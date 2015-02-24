#!/usr/bin/python
'''
This script will be run on start-up to evaluate the Docker link environment 
variables and automatically generate upstream and location modules for 
reverse-proxying and load-balancing.

It looks for environment variables in the following formats:
<service-name>_<service-instance-id>_PORT_80_TCP_ADDR=x.x.x.x
<service-name>_PATH=<some path>

Optional/Conditional environment variables:
<service-name>_BALANCING_TYPE=[ip_hash|least_conn] (optional)
<service-name>_EXPOSE_PROTOCOL=[http|https|both] (optional - default: http)
<service-name>_HOSTNAME=<vhostname> (required if <service-name>_EXPOSE_PROTOCOL is https or both)
<env-formatted-vhostname>_SSL_CERTIFICATE=<something.pem> (required if the vhost will need ssl support)
<env-formatted-vhostname>_SSL_CERTIFICATE_KEY=<something.key> (required if the vhost will need ssl support)

And will build an nginx config file.

Example:

    # automatically created environment variables (docker links)
    WEBAPP_1_PORT_80_TCP_ADDR=192.168.0.2
    WEBAPP_2_PORT_80_TCP_ADDR=192.168.0.3
    WEBAPP_3_PORT_80_TCP_ADDR=192.168.0.4
    API_1_PORT_80_TCP_ADDR=192.168.0.5
    API_2_PORT_80_TCP_ADDR=192.168.0.6

    # special environment variables
    WEBAPP_PATH=/
    WEBAPP_BALANCING_TYPE=ip_hash
    WEBAPP_EXPOSE_PROTOCOL=both
    WEBAPP_HOSTNAME=www.example.com
    API_PATH=/api/
    API_EXPOSE_PROTOCOL=https
    API_HOSTNAME=www.example.com
    WWW_EXAMPLE_COM_SSL_CERTIFICATE=something.pem
    WWW_EXAMPLE_COM_SSL_CERTIFICATE_KEY=something.key

Generates (/etc/nginx/sites-enabled/proxy.conf):

    upstream webapp {
        ip_hash;
        server 192.168.0.2;    
        server 192.168.0.3;    
        server 192.168.0.4;    
    }

    upstream api {
        server 192.168.0.5;
        server 192.168.0.6;
    }

    server {
        listen 80;
        listen [::]:80 ipv6only=on;
        server_name www.example.com;

        root /usr/share/nginx/html;

        location / {
            proxy_pass http://webapp:80;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }

    server {
        listen 443;
        server_name www.example.com;
    
        root html;
        index index.html index.htm;
    
        ssl on;
        ssl_certificate ssl/something.pem;
        ssl_certificate_key ssl/something.key;
     
        ssl_session_timeout 5m;
    
        ssl_protocols SSLv3 TLSv1 TLSv1.1 TLSv1.2;
        ssl_ciphers "HIGH:!aNULL:!MD5 or HIGH:!aNULL:!MD5:!3DES";
        ssl_prefer_server_ciphers on;

        root /usr/share/nginx/html;

        location / {
            proxy_pass http://webapp:80;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        location /api/ {
            proxy_pass http://api:80;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }

'''

import sys
import os
import re
import argparse
import json
import textwrap
import subprocess
from jinja2 import Environment, FileSystemLoader

env = Environment(
    loader=FileSystemLoader(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates')
        )
    )
parser = argparse.ArgumentParser(
    description='Docker-based Nginx Load Balancer Startup Script', 
    formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument(
    '-t', 
    '--test', 
    action='store', 
    choices=['conf', 'parse'], 
    help=textwrap.dedent('''\
    Test against your environment variables 
    without modifying the config files.
        'conf' - Preview the generated Nginx config file's contents.
        'parse' - View a detailed parsing of the environment.
    '''))
parser.add_argument(
    '-o',
    '--output-file',
    action='store',
    help='Location where the generated Nginx config file will be placed.',
    default='/etc/nginx/sites-enabled/proxy.conf'
    )

def build_conf(hosts, services):
    template = env.get_template('proxy.conf')
    return template.render(hosts=hosts, services=services)

def parse_env(env=os.environ):
    prefix = env.get('ENV_PREFIX')
    if prefix:
        prefix = prefix.upper() + '_'
        print 'Using prefix: %s' % (prefix)
    else:
        prefix = ''
        print 'No fig prefix found.'

    link_pattern = re.compile(r'^%s(?P<service_name>[a-zA-Z_]+)(_[\d]+)?_PORT_(?P<service_port>[\d]+)_TCP_ADDR$' % (prefix))

    services = {}
    hosts = {}

    # find services and collect addresses
    for var, value in env.iteritems():
        m = link_pattern.match(var)
        if m:
            service_name = m.group('service_name')
            service_port = int(m.group('service_port'))
            if service_port != 80:
                service_port = env.get('%s_REMOTE_PORT' % (service_name))
                if not service_port:
                    continue
            if service_name in services:
                services[service_name]['addresses'].append(value)
            else:
                print 'Found service: %s' % service_name
                services[service_name] = {
                    'addresses': [value],
                    'port': service_port,
                    'balancing_type': None,
                }

    # find service details
    for service_name, value in services.iteritems():
        path = value['location'] = env.get('%s_PATH' % (service_name))
        remote_path = value['remote_path'] = env.get('%s_REMOTE_PATH' % (service_name), '/')
        balancing_type = value['balancing_type'] = env.get('%s_BALANCING_TYPE' % (service_name))
        expose_protocol = value['expose_protocol'] = env.get('%s_EXPOSE_PROTOCOL' % (service_name), 'http')
        hostname = value['host'] = env.get('%s_HOSTNAME' % (service_name))

        assert path != None, 'Could not find %s_PATH environment variable for service %s.' % (service_name, service_name)
        assert balancing_type in [None, 'ip_hash', 'least_conn'], 'Invalid value for %s_BALANCING_TYPE: %s, must be "ip_hash", "least_conn", or nonexistant.' % (service_name, balancing_type)
        assert expose_protocol in ['http', 'https', 'both'], 'Invalid value for %s_EXPOSE_PROTOCOL: %s, must be "http", "https", or "both"' % (service_name, expose_protocol)
        assert expose_protocol == 'http' or hostname != None, 'With %s_EXPOSE_PROTOCOL=%s, you must supply %s_HOSTNAME.' % (service_name, expose_protocol, service_name)

        if hostname == None:
            hostname = value['host'] = '0.0.0.0'

        if hosts.get(hostname) == None:
            hosts[hostname] = {
                'protocols': {'http': False, 'https': False},
                'services': []
            }

        hosts[hostname]['services'].append(service_name)

        if expose_protocol == 'both':
            hosts[hostname]['protocols']['http'] = True
            hosts[hostname]['protocols']['https'] = True
        else:
            hosts[hostname]['protocols'][expose_protocol] = True

    for hostname, value in hosts.iteritems():
        formatted_hostname = format_hostname(hostname)
        if value['protocols']['https']:
            ssl_certificate = env.get('%s_SSL_CERTIFICATE' % formatted_hostname)
            ssl_certificate_key = env.get('%s_SSL_CERTIFICATE_KEY' % formatted_hostname)

            assert ssl_certificate, 'SSL certificate .pem not provided for https host: %s, please set %s_SSL_CERTIFICATE' % (hostname, formatted_hostname) 
            assert ssl_certificate_key, 'SSL certificate .key not provided for https host: %s, please set %s_SSL_CERTIFICATE_KEY' % (hostname, formatted_hostname)
            assert os.path.isfile(os.path.join('/etc/nginx/ssl/', ssl_certificate)), 'SSL certificate file: %s could not be found for %s' (ssl_certificate, hostname)
            assert os.path.isfile(os.path.join('/etc/nginx/ssl/', ssl_certificate_key)), 'SSL certificate file: %s could not be found for %s' (ssl_certificate_key, hostname)

            value['ssl_certificate'] = ssl_certificate
            value['ssl_key'] = ssl_certificate_key

    return hosts, services

def format_hostname(hostname):
    return hostname.replace('.', '_').upper()

if __name__ == "__main__":
    args = parser.parse_args()

    hosts, services = parse_env()
    if args.test == 'parse':
        print "Services:"
        print "%s\n" % json.dumps(services, sort_keys=True, indent=4, separators=(',', ': '))
        print "Hosts:"
        print "%s" % json.dumps(hosts, sort_keys=True, indent=4, separators=(',', ': '))
        exit(0)

    conf_contents = build_conf(hosts, services)
    sys.stdout.flush()
    if args.test == 'conf':
        print "Contents of proxy.conf:%s" % conf_contents.replace('\n', '\n    ')
        exit(0)

    f = open(args.output_file, 'w')
    f.write(conf_contents)
    f.close()

    sys.stdout.write("Starting Nginx...\n")
    sys.stdout.flush()

    p = subprocess.Popen(['nginx'], stdout=subprocess.PIPE, bufsize=0)
    while True:
        char = p.stdout.read(1)
        sys.stdout.write(char)
        sys.stdout.flush()
        if char == '' and p.poll() != None:
            break

    p.stdout.close()












