#!/bin/sh
set -e
set -x

protoc_ver=0.9.3

BUILD="$HOME/.protoc-build"
if [ ! -d "$BUILD" ]; then
	mkdir -p "$BUILD"
fi
cd "$BUILD"

wget https://github.com/google/protobuf/releases/download/v2.6.1/protobuf-2.6.1.tar.gz
tar xzf protobuf-2.6.1.tar.gz
cd protobuf-2.6.1
sudo apt-get update
sudo apt-get install build-essential
sudo ./configure
sudo make
sudo make check
sudo make install 
sudo ldconfig
protoc --version

