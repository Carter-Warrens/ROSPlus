#!/usr/bin/env bash
set -euo pipefail
# Official ROS 2 Jazzy apt installation, limited to Ubuntu 24.04.
# Adds the ROS apt repository and installs development/runtime packages.
. /etc/os-release
if [[ "$ID" != ubuntu || "$VERSION_ID" != 24.04 ]]; then
  echo 'This script supports Ubuntu 24.04 only.' >&2; exit 1
fi
sudo apt-get update
sudo apt-get install -y curl ca-certificates software-properties-common python3
sudo add-apt-repository -y universe
rosplus_setup_tmp="$(mktemp -d)"
trap 'rm -rf "$rosplus_setup_tmp"' EXIT
curl --fail --location --proto '=https' https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest -o "$rosplus_setup_tmp/release.json"
rosplus_source_version="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["tag_name"])' "$rosplus_setup_tmp/release.json")"
if [[ ! "$rosplus_source_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then echo 'Unexpected apt-source version' >&2; exit 1; fi
curl --fail --location --proto '=https' "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${rosplus_source_version}/ros2-apt-source_${rosplus_source_version}.noble_all.deb" -o "$rosplus_setup_tmp/ros2-apt-source.deb"
sudo dpkg -i "$rosplus_setup_tmp/ros2-apt-source.deb"
sudo apt-get update
sudo apt-get install -y ros-jazzy-ros-base ros-jazzy-demo-nodes-py ros-jazzy-demo-nodes-cpp ros-jazzy-example-interfaces ros-dev-tools build-essential cmake python3-venv
printf '\nROS 2 installed. Start a new shell or run: source /opt/ros/jazzy/setup.bash\n'
