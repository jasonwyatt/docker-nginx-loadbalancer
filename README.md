# docker-nginx-loadbalancer

This image will auto-generate its own config file for a load-balancer.

It looks for environment variables in the following formats:

    <service-name>_<service-instance-id>_PORT_80_TCP_ADDR=x.x.x.x
    <service-name>_PATH=<some path>

Optional/Conditional environment variables:

    <service-name>_REMOTE_PORT=<remoteport> (optional - default: 80)
    <service-name>_REMOTE_PATH=<remotepath> (optional - default: /)
    <service-name>_BALANCING_TYPE=[ip_hash|least_conn] (optional)
    <service-name>_EXPOSE_PROTOCOL=[http|https|both] (optional - default: http)
    <service-name>_HOSTNAME=<vhostname> (required if <service-name>_EXPOSE_PROTOCOL is https or both)
    <service-name>_ACCESS_LOG=[/dev/stdout|off] (optional - default: /dev/stdout)
    <service-name>_ERROR_LOG=[/dev/stdout|/dev/null] (optional - default: /dev/stdout)
    <service-name>_LOG_LEVEL=[emerg|alert|crit|error|warn|notice|info|debug'] (optional - default: error)
    <env-formatted-vhostname>_SSL_CERTIFICATE=<something.pem> (required if the vhost will need ssl support)
    <env-formatted-vhostname>_SSL_CERTIFICATE_KEY=<something.key> (required if the vhost will need ssl support)
    <env-formatted-vhostname>_SSL_DHPARAM=<dhparam.pem> (required if the vhost will need ssl support)
    <env-formatted-vhostname>_SSL_CIPHERS=<"colon separated ciphers wrapped in quotes"> (required if the vhost will need ssl support)
    <env-formatted-vhostname>_SSL_PROTOCOLS=<protocol (e.g. TLSv1.2)> (required if the vhost will need ssl support)

And will build an nginx config file.

Example:

    # automatically created environment variables (docker links)
    WEBAPP_1_PORT_80_TCP_ADDR=192.168.0.2
    WEBAPP_2_PORT_80_TCP_ADDR=192.168.0.3
    WEBAPP_3_PORT_80_TCP_ADDR=192.168.0.4
    API_1_PORT_80_TCP_ADDR=192.168.0.5
    API_2_PORT_80_TCP_ADDR=192.168.0.6
    TOMCAT_1_PORT_8080_TCP_ADDR=192.168.0.7
    TOMCAT_2_PORT_8080_TCP_ADDR=192.168.0.8

    # special environment variables
    WEBAPP_PATH=/
    WEBAPP_BALANCING_TYPE=ip_hash
    WEBAPP_EXPOSE_PROTOCOL=both
    WEBAPP_HOSTNAME=www.example.com
    WEBAPP_ACCESS_LOG=off
    WEBAPP_ERROR_LOG=/dev/stdout
    WEBAPP_LOG_LEVEL=emerg
    API_PATH=/api/
    API_EXPOSE_PROTOCOL=https
    API_HOSTNAME=www.example.com
    WWW_EXAMPLE_COM_SSL_CERTIFICATE=ssl/something.pem
    WWW_EXAMPLE_COM_SSL_CERTIFICATE_KEY=ssl/something.key
    WWW_EXAMPLE_COM_SSL_DHPARAM=ssl/dhparam.pem
    WWW_EXAMPLE_COM_SSL_CIPHERS="ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-SHA384:ECDHE-RSA-AES256-SHA384:ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES128-SHA256"
    WWW_EXAMPLE_COM_SSL_PROTOCOLS=TLSv1.2
    TOMCAT_PATH=/javaapp
    TOMCAT_REMOTE_PORT=8080
    TOMCAT_REMOTE_PATH=/javaapp

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

    upstream tomcat {
        server 192.168.0.7;
        server 192.168.0.8;
    }

    server {
        listen 80;
        listen [::]:80 ipv6only=on;
        server_name www.example.com;

        error_log /dev/stdout emerg;
        access_log off;

        root /usr/share/nginx/html;

        location / {
            proxy_pass http://webapp:80/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_buffering off;
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
        
        # Diffie-Hellman parameter for DHE ciphersuites, recommended 2048 bits
        ssl_dhparam ssl/dhparam.pem;

        ssl_session_timeout 5m;

        ssl_protocols TLSv1.2;
        ssl_ciphers "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-SHA384:ECDHE-RSA-AES256-SHA384:ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES128-SHA256";
        ssl_prefer_server_ciphers on;

        root /usr/share/nginx/html;

        location / {
            proxy_pass http://webapp:80/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_buffering off;
        }
        location /api/ {
            proxy_pass http://api:80/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_buffering off;
        }
    }

    server {
        listen 80;
        listen [::]:80 ipv6only=on;

        root /usr/share/nginx/html;

        location /javaapp {
            proxy_pass http://tomcat:8080/javaapp;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_buffering off;
        }
    }
