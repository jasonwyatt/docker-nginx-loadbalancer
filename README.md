# docker-nginx-loadbalancer

This image will auto-generate its own config file for a load-balancer.

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
    
        ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
        ssl_ciphers "HIGH:!aNULL:!MD5 or HIGH:!aNULL:!MD5:!3DES";
        ssl_prefer_server_ciphers on;

        root /usr/share/nginx/html;

        location / {
            proxy_pass http://webapp:80/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        location /api/ {
            proxy_pass http://api:80/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
