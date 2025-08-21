#!/bin/bash

docker build -t academygram .

docker run --rm -p 2750:2750 academygram 
