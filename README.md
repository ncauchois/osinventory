OSinventory: Lists OpenStack resources in a project
============================================

`osinventory` is a client side script allowing an OpenStack user to list resources that are deployed/available in his/her project.

Installation
------------

Get `osinventory` source code:

    $ git clone git@github.com:cloudwatt/osinventory.git

This script uses the OpenStack clients to connect to the services and retrieve all information about resources that where deployed in the project.

These clients can be installed by using the `requirements.txt` if they are not already available:

    $ sudo pip install -r requirements.txt


Usage
-----

Available options can be displayed by using `osinventory.py -h`:

    $python osinventory.py  --help
    usage: osinventory.py [-h] username password project auth_url

    Print resources from an Openstack project or user

    positional arguments:
        username    A user name with access to the project
        password    The user's password
        project     Name of project
        auth_url    Authentication URL
        region_name Region to use

    optional arguments:
    -h, --help  show this help message and exit
    
Example
-------
    To execute the script you can either:
    source your openrc.sh so that your criedentails are taken as os enviroment variable 
    $ source openrc.sh
    $ python osinventory.py
    or:
    Pass your openstack cridentails as parameters where running the script:
    python osinventory.py -u <username> -pwd <password>  -p <project_id> -url <authentification_url> -r <region_name>

    To store the inventory result in a file, use the f flag as following:
    $ python osinventory.py -f true
    A file called list_ressources.txt will be created in the current directory containing the list of your openstack ressources

Listed resources
-------

The following resources will be listed:

* Nova and Cinder Quoats and Usage (limits)
* Instances
* Security groups/rules
* Key paris
* Owned or Private Images, Shared Images, Public Images, Cloudwatt Images and Images Snapshots
* Volumes/volumes snapshots/volumes backups
* Networks
* Routers
* LBASS/LBASS Members
* Stacks


License / Copyright
-------------------

This software is released under the MIT License.

Copyright (c) 2014 Cloudwatt

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

