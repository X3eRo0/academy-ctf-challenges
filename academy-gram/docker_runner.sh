#!/bin/bash

docker build -t academygram .

docker run --rm -p 5000:5000 academygram 
