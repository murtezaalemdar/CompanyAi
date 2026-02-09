#!/bin/bash
sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/14/main/postgresql.conf
systemctl restart postgresql
echo "PostgreSQL updated and restarted."
