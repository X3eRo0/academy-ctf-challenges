#!/bin/bash

docker run -d -p5000:5000 ping
docker ps -n 1
