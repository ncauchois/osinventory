
import argparse
import logging
import os
import sys
import prettytable
import inspect 
import threading 
import time

import keystoneclient.v2_0.client as keystone
from keystoneauth1.identity import v2
from keystoneauth1 import session
import novaclient.client as nova
from novaclient import utils as nova_utils
import cinderclient.client as cinder
from glanceclient.v1 import client as glance
import neutronclient.v2_0.client as neutron
import heatclient.client as heat
import requests.packages.urllib3

requests.packages.urllib3.disable_warnings()

logger = logging.getLogger()


def format_flavor_details(f):
    #f = client.flavors.get(flavor_id).to_dict()
    return '|'.join([ str(f['vcpus']) + 'VCPU', str(f['ram']) +
                      'MB RAM', str(f['disk'])+'GB Disk'])

def get_server_image_name(client, server):
    try:
        name = client.images.get(server['image']['id']).to_dict().get('name', '-')
    except Exception as e:
        name = '--'
    return name

def get_image_category(image, user_tenant_id):
    """Get image category

    """
    cw_origin = image.properties.get('cw_origin')
    cw_bundle = image.properties.get('cw_bundle')
    cw_haas = image.properties.get('cw_haas')
    if image.is_public:
        if cw_origin and cw_origin.lower() == 'cloudwatt':
            if cw_haas and cw_haas.lower().strip() == 'haas':
                return 'haas'
            elif cw_bundle:  # cw_bundle can take different values.
                return 'orchestration'
            return 'cloudwatt'
        return 'community'
    if image.owner == user_tenant_id:
        return 'project'
    return 'shared'


def session_create(config):
    auth = v2.Password(auth_url=config['auth_url'],
                       username=config['username'],
                       password=config['password'],
                       tenant_id=config['project'])
    return session.Session(auth=auth)

def format_network(name,liste):
    try:
        network = name+'='
        for e in liste:
            network += e['addr']+':'+e['OS-EXT-IPS:type']+','
        return network.rstrip(',')
    except KeyError as e:
        pass

class OpenstackUtils():
    def __init__(self, config):
        global sess
        sess = session_create(config)
        self.keystone_client = keystone.Client(username=config['username'],
                                               password=config['password'],
                                               tenant_id=config['project'],
                                               auth_url=config['auth_url'],
                                               region_name=config['region_name'])

        heat_url = self.keystone_client\
                       .service_catalog.url_for(service_type='orchestration',
                                            endpoint_type='publicURL')


        self.nova_client = nova.Client('2.1',region_name=config['region_name'], session=sess)
        self.cinder_client = cinder.Client('2', region_name=config['region_name'], session=sess)
        self.glance_client = glance.Client('2', region_name=config['region_name'], session=sess)
        self.neutron_client = neutron.Client(region_name=config['region_name'], session=sess)
        self.heat_client = heat.Client('1', region_name=config['region_name'], endpoint=heat_url, session=sess)

        functions = []
        threads = []
        self.print_servers=self.print_ips=self.print_scgps=self.print_keys=False
        self.print_volumes=self.print_snapshots=self.print_backups=False
        self.print_netowrks=self.print_routers=False
        self.print_images=self.print_owned_images=self.print_shared_imges=False
        self.print_cloudwatt_images=self.print_snapshots_images=False
        self.print_lbass=self.print_members=self.print_stacks=False

        
        def get_limits():
            self.nova_limits = self.nova_client.limits.get().to_dict()['absolute']
            self.cinder_limits = self.cinder_client.limits.get().to_dict()['absolute']
        functions.append(get_limits)

        def get_servers():
            self.flavors_dict = {}
            self.servers = map(lambda x:x.to_dict(), self.nova_client.servers.list())
            map(lambda x:self.flavors_dict.update({x.id:x}), self.nova_client.flavors.list())
        functions.append(get_servers)

        def get_floating_ips():
            self.ips = self.nova_client.floating_ips.list()
        functions.append(get_floating_ips)

        def get_securitygps():
            self.securitygps = map(lambda x:x.to_dict(), self.nova_client\
                                                   .security_groups.list())
        functions.append(get_securitygps)

        def get_keys():
            self.keys = self.nova_client.keypairs.list()
        functions.append(get_keys)    

        def get_images(project_id=config['project']):
            self.images_dict = {}
            self.images = []
            for image in self.glance_client.images.list():
                self.images.append(image)
            copy_images = self.images
            map(lambda x:self.images_dict.update({x.id:x}), copy_images)

        functions.append(get_images)

        def get_volumes():
            self.volumes =  self.cinder_client.volumes.list()
        functions.append(get_volumes)

        def get_volumes_snapshots():
            self.snapshots = self.cinder_client.volume_snapshots.list()
        functions.append(get_volumes_snapshots)

        def get_volumes_backups():
            self.backups = self.cinder_client.backups.list()
        functions.append(get_volumes_backups)    

        def get_networks():
            self.routers = self.neutron_client.list_routers()['routers']
            self.networks = self.neutron_client.list_networks()['networks']
            self.subnets = self.neutron_client.list_subnets()['subnets']
        functions.append(get_networks)

        def get_lbass():
               self.lbass = self.neutron_client.list_pools()['pools']
               self.members = self.neutron_client.list_members()['members']
        functions.append(get_lbass)

        def get_stacks():
            self.stacks = self.heat_client.stacks.list()
        functions.append(get_stacks)


        for func in functions:
            t = threading.Thread(name=func, target=func)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

    def print_ressources(self):

        #Print Limits and Quotas Usage
        nova_limits = self.nova_limits
        cinder_limits = self.cinder_limits
        limits_table = prettytable.PrettyTable(['Resource', 'Max', 'Used'])
        limits_table.add_row(['Servers',nova_limits['maxTotalInstances'],
                       nova_limits['totalInstancesUsed']])
        limits_table.add_row(['Volumes',cinder_limits['maxTotalVolumes'],
                       cinder_limits['totalVolumesUsed']])
        limits_table.add_row(['V_Snapshots',cinder_limits['maxTotalSnapshots'],
                       cinder_limits['totalSnapshotsUsed']])
        limits_table.add_row(['V_Backups',cinder_limits['maxTotalBackups'],
                       cinder_limits['totalBackupsUsed']])

        limits_table.add_row(['RAM (MB)',nova_limits['maxTotalRAMSize'],
                       nova_limits['totalRAMUsed'] ])
        limits_table.add_row(['Cores',nova_limits['maxTotalCores'],
                       nova_limits['totalCoresUsed'] ])
        limits_table.add_row(['VolumesGigabytes',
                       cinder_limits['maxTotalBackupGigabytes'],
                       cinder_limits['totalGigabytesUsed'] ])
        limits_table.add_row(['BackupGigabyte',
                       cinder_limits['totalBackupGigabytesUsed'],
                       cinder_limits['totalBackupGigabytesUsed'] ])


        #Print List of Servers
        columns = ['ID', 'Name', 'Status', 'Image Name', 'Flavor Details','Key Name', 'Networks']
        servers_table = prettytable.PrettyTable(columns)
        for s in self.servers:
            self.print_networks = True
            networks = ''
            if s['addresses']:
                networks =  s['addresses'].keys()[0]+'='
                for value in s['addresses'].values():
                    for v in  value:
                        networks += v['addr']+', '
            s['networks'] = networks.rstrip(', ')
            flavor = self.flavors_dict[s['flavor']['id']].to_dict()
            s['flavor details'] = format_flavor_details(flavor)
            try:
                s['image name'] = self.images_dict[s['image']['id']].to_dict().get('name','-')
            except Exception as e:
                s['image name'] = '-'            	

            servers_table.add_row([s['id'], s.get('name', '-'), s['status'],s.get('image name', '-'),
                           s['flavor details'], s['key_name'], s['networks']])  

           
        #Print List of IPs
        columns = ['ID', 'Fixed IP', 'IP', 'Server ID']
        ips_table = prettytable.PrettyTable(columns)
        for ip in self.ips:
            self.print_ips = True
            ip_dict = ip.to_dict()
            if not ip.instance_id:
                ip.instance_id = '***Not Used***'
            if not ip.fixed_ip:
                ip.instance_id = '-'
            ips_table.add_row([ip.id, ip.fixed_ip, ip.ip,
                           ip.instance_id ])

        #Print List of Keys
        columns = ['Name', 'Fingerprint']
        keys_table = prettytable.PrettyTable(columns)
        for k in self.keys:
            self.print_keys = True
            keys_table.add_row([k.name,k.fingerprint])


        #Print List of Secgps
        columns = ['Name', 'Description', 'Protocol','From Port', 'To Port', 'IP Range']
        secgps_table = prettytable.PrettyTable(columns)
        for secgp in self.securitygps:
            self.print_scgps = True
            secgps_table.add_row([secgp.get('name', '-'), secgp['description'], '', '', '', ''])
            for sec in filter(None,secgp['rules']):
                secgps_table.add_row(['', '', sec['ip_protocol'], sec['from_port'],
                                sec['to_port'], sec['ip_range']])

        #Print List of Images
        images = []
        cloudwatt_images = False
        shared_images = False
        snapshots = False
        all_images = False
        owned_images = False

        columns = ['ID', 'Name', 'Status','Size', 'Disk format', 'Created_at']
        owned_table = prettytable.PrettyTable(columns)
        shared_table = prettytable.PrettyTable(columns)
        cloudwatt_table = prettytable.PrettyTable(columns)
        snapshots_table = prettytable.PrettyTable(columns)
        all_table = prettytable.PrettyTable(columns)

        for img in self.images:
            self.print_images = True
            category = get_image_category(img, config['project'])
            if category == 'project':
                self.print_owned_images = True
                owned_table.add_row([img.id, img.to_dict().get('name','-'), img.status,img.size,
                img.disk_format, img.created_at])
            if category == 'shared':
                self.print_shared_imges = True
                shared_table.add_row([img.id, img.to_dict().get('name','-'), img.status,img.size,
                img.disk_format, img.created_at])
            elif category =='cloudwatt':
                self.print_cloudwatt_images = True
                cloudwatt_table.add_row([img.id, img.to_dict().get('name','-'), img.status,img.size,
                img.disk_format, img.created_at])
             
            if 'image_type' in img.properties:
                if img.properties['image_type'] == "snapshot":
                    self.print_snapshots_images = True
                    snapshots_table.add_row([img.id, img.to_dict().get('name','-'), img.status,img.size,
                    img.disk_format, img.created_at])
            all_table.add_row([img.id, img.to_dict().get('name','-'), img.status,img.size,
                               img.disk_format, img.created_at])


        #Print List of Volumes
        columns = ['ID', 'Status', 'Name',
                   'Size', 'Volume Type', 'Bootable',
                   'Attached_to', 'Snapshot ID', 'Created at']
        volumes_table = prettytable.PrettyTable(columns)
        for volume in self.volumes:
            self.print_volumes = True
            if volume.snapshot_id is None:
                volume.snapshot_id = '***-***'
            volume.Attached_to = '***Not Attached***'
            for attch in volume.attachments:
                try:
                    volume.Attached_to = self.nova_client.servers.get(attch['server_id']).to_dict()['name']
                except Exception as e:
                    pass
            volumes_table.add_row([volume.id, volume.status, volume.to_dict().get('name', '-'), volume.size,
                          volume.volume_type, volume.bootable,
                          volume.Attached_to, volume.snapshot_id,
                          volume.created_at])

        #print Volumes Snapshots
        columns = ['ID', 'Status', 'Name', 'Description','Size', 'Created_at']
        v_snapshots_table = prettytable.PrettyTable(columns)

        for s in self.snapshots:
        	self.print_snapshots = True
        	v_snapshots_table.add_row([s.id, s.status, s.to_dict().get('name', '-'), s.description,
                                     s.size, s.created_at])

        #print Volumes Backups
        backups_table = prettytable.PrettyTable(columns)

        for b in self.backups:
            self.print_backups = True
            backups_table.add_row([s.id, s.status, s.to_dict().get('name', '-'), s.description,
                                     s.size, s.created_at])
      
        routers_table = prettytable.PrettyTable(['ID', 'Name', 'Status', 'Network ID'])
        networks_table = prettytable.PrettyTable(['Name', 'Status', 'Subnet','Subnet ID',
                                             'Subnet Allocation Pool', 'Gateway IP',
                                             'CIDR'])

        networks = {}
        subnets = {}
        routers = {}
        routers_details = []
        for subnet in self.subnets:
            subnets[subnet['id']] = subnet

        routers = self.routers

        for network in self.networks:
            network['subnet_details'] = []
            network['router_details'] = []
            for subnet in network['subnets']:
                try:
                    network['subnet_details'].append(subnets[subnet])
                    networks[network['id']] = network
                except Exception as e:
                    networks[network['id']] = network

        for router in routers:
            self.print_routers = True
            try:
                router_table.add_row([router['id'], router['name'], router['status'],
                                      router['external_gateway_info']['network_id']])

                networks[router['external_gateway_info']['network_id']]\
                         ['router_details'].append(router)
            except Exception as e:
                routers_table.add_row([router['id'], router['name'], router['status'],'---'])

        for network in networks.values():
            self.print_netowrks = True
            networks_table.add_row([network.get('name', '-'), network['status'], '','',  '', '',  ''])
            for subnet in network['subnet_details']:
                if not subnet['name']:
                    subnet['name'] = '---'
                networks_table.add_row(['', '', subnet.get('name', '-'), subnet['id'], subnet['allocation_pools'],
                                        subnet['gateway_ip'], subnet['cidr']])

        #Print List Of LBASS
        lbass = self.lbass
        members = self.members
        columns = ['ID', 'Name', 'Status', 'Provider',
                   'lb_method', 'admin_state_up', 'Protocol']
        lbass_table = prettytable.PrettyTable(columns)
        members_table = prettytable.PrettyTable(['Name', 'Member ID', 'Member Status',
                                                 'Member Address', 'Member Protocol Port'])
        for lbas in lbass:
            self.print_lbass = True
            lbas['members'] = []
            members_table.add_row([lbas.get('name', '-'), '', '', '', ''])
            for m in members:
                self.print_members = True
                if m['pool_id'] == lbas['id'] :
                    members_table.add_row(['', m['id'], m['status'], m['address'], m['protocol_port'] ])
            lbass_table.add_row([lbas['id'], lbas.get('name', '-'), lbas['status'],
                          lbas['provider'], lbas['lb_method'],
                          lbas['admin_state_up'], lbas['protocol']])

        #Print List of Stacks
        stacks = self.stacks
        columns = ['Stack_Name', 'Creation Time', 'Stack Status', 'Stack Status Reason']
        stacks_table = prettytable.PrettyTable(columns) 
        for stack in stacks :
            self.print_stacks = True
            stacks_table.add_row([stack.to_dict().get('stack_name', '-'), stack.creation_time, stack.stack_status, stack.stack_status_reason])

        print '\nQuotas and Usage Limits\n'
        print limits_table

        if self.print_servers:
            print '\nList of Servers\n'
            print servers_table  

        if self.print_ips:
            print '\nList of Floating IPs\n'
            print ips_table

        if self.print_keys:
            print '\nList of Keys\n'
            print keys_table

        if self.print_scgps:
            print '\nList of Security Groupes\n'
            print secgps_table

        if self.print_owned_images:
            print '\nList of Owned Images\n'
            print owned_table
        if self.print_shared_imges:
            print '\nList of Shared Images\n'
            print shared_table
        if self.print_cloudwatt_images:
            print '\nList of Cloudwatt Images\n'
            print cloudwatt_table
        if self.print_snapshots_images:
            print '\nList of Snapshots\n'
            print snapshots_table
        if self.print_images:
            print '\nALL Available Images\n'
            print all_table

        if self.print_volumes:
            print '\nList of Volumes\n'
            print volumes_table

        if self.print_snapshots:
            print self.print_snapshots
            print '\nList of Volumes Snapshots\n'
            print v_snapshots_table

        if self.print_backups:
            print '\nList of Volumes Backups\n'
            print backups_table

        if self.print_netowrks:
            print '\nList of Networks\n'
            print networks_table
        if self.print_routers:
            print '\nList of Routers\n'
            print routers_table

        if self.print_lbass:
            print '\nList of LBASS\n'
            print lbass_table
        if self.print_members:
            print '\nLBASS Members\n'
            print members_table

        if self.print_stacks:
            print '\nList of Stacks\n'
            print stacks_table

        if(config['file']):
            with open('list_ressources.txt', 'w') as w:
                w.write('\nQuotas and Usage Limits\n')  
                w.write(str(limits_table))

                if self.print_servers:
                    w.write('\nList of Servers\n')
                    w.write(str(servers_table))  

                if self.print_ips:
                    w.write('\nList of Floating IPs\n')
                    w.write(str(ips_table))

                if self.print_keys:
                    w.write('\nList of Keys\n')
                    w.write(str(keys_table))

                if self.print_scgps:
                    w.write('\nList of Security Groupes\n')
                    w.write(str(secgps_table))

                if self.print_owned_images:
                    w.write('\nList of Owned Images\n')
                    w.write(str(owned_table))
                if self.print_shared_imges:
                    w.write('\nList of Shared Images\n')
                    w.write(str(shared_table))
                if self.print_cloudwatt_images:
                    w.write('\nList of Cloudwatt Images\n')
                    w.write(str(cloudwatt_table))
                if self.print_snapshots_images:
                    w.write('\nList of Snapshots\n')
                    w.write(str(snapshots_table))
                if self.print_servers:
                    w.write('\nALL Available Images\n')
                    w.write(str(all_table))

                if self.print_volumes:
                    w.write('\nList of Volumes\n')
                    w.write(str(volumes_table))

                if self.print_snapshots:
                    w.write('\nList of Volumes Snapshots\n')
                    w.write(str(snapshots_table))

                if self.print_backups:
                    w.write('\nList of Volumes Backups\n')
                    w.write(str(backups_table))

                if self.print_netowrks:
                    print '\nList of Networks\n'
                    print networks_table
                if self.print_routers:
                    print '\nList of Routers\n'
                    print routers_table

                if self.print_lbass:
                    w.write('\nList of LBASS\n')
                    w.write(str(lbass_table))
                if self.print_members:
                    w.write('\nLBASS Members\n')
                    w.write(str(members_table))

                if self.print_stacks:
                    w.write('\nList of Stacks\n')
                    w.write(str(stacks_table))



def main():
    parser = argparse.ArgumentParser(description=
                                     'Print resources from an Openstack'\
                                     'project'
                                     )
    parser.add_argument('-u', '--username', help='Openstack Username',
                        default=os.environ.get('OS_USERNAME', None),
                        required=False)
    parser.add_argument('-pwd', '--password', help='Openstack Password',
                        default=os.environ.get('OS_PASSWORD', None),
                        required=False)
    parser.add_argument('-p', '--project', help='Openstack project',
                        default=os.environ.get('OS_TENANT_ID', None),
                        required=False)
    parser.add_argument('-url', '--auth_url',
                        help='Keystone Authentification URL',
                        default=os.environ.get('OS_AUTH_URL', None),
                        required=False)
    parser.add_argument('-r', '--region_name', help='Region Name',
                        default=os.environ.get('OS_REGION_NAME', None),
                        required=False)
    parser.add_argument('-f', '--file', help='save output to file',
                        default=None,
                        required=False)
    args = parser.parse_args()

    global config
    config = {}
    config['username'] = args.username
    config['password'] = args.password
    config['project'] = args.project
    config['auth_url'] = args.auth_url
    config['region_name'] = args.region_name
    config['file'] = args.file

    missing = []
    for arg in config.keys():
        if arg != 'file' and config[arg] is None:
            missing.append(arg)

    if missing:
        print 'please export or provide as parameters the following:'
        print missing
        sys.exit(0)

    start_time = time.time()
    print 'Getting Ressources, Please Wait......'
    utility = OpenstackUtils(config)
    utility.print_ressources()
    print("--- %s seconds ---" % (time.time() - start_time))


if __name__ == "__main__":
    main()
