#!/bin/bash

# SPDX-FileCopyrightText: The pynxtools-xas Authors
#
# This file is part of pynxtools-xas.
#
# SPDX-License-Identifier: Apache-2.0
function update_ref_file {
  local FOLDER=$1
  local NXDL=$2
  cd "$FOLDER"
  echo "Update $FOLDER reference file for $NXDL"
  files=$(find . -maxdepth 1 -type f \( ! -name "*.log" -a ! -name "*.nxs" -a ! -name "ref_output.txt" \))
  pynx convert ${files[@]} --reader xas --nxdl "$NXDL" --ignore-undocumented --output "${FOLDER}_ref.nxs"
  cd ..
}

# folder:nxdl
cases=(
  # "specs_xy_aey:NXxas"
  "esrf_fluorescence_id21:NXxas"
  # "esrf_transmission_exafs:NXxas_trans"
  # "oscars_xdi_transmission:NXxas_trans"
)

project_dir=$(dirname $(dirname $(realpath $0)))
cd $project_dir/tests/data

for case in "${cases[@]}"; do
  IFS=":" read -r folder nxdl <<< "$case"
  update_ref_file "$folder" "$nxdl"
done
