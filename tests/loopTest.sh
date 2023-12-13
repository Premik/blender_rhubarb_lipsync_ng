#!/bin/bash

# Directory where the pytest output files will be stored
output_dir="/tmp/pytest"

# Create the output directory if it doesn't exist
mkdir -p "$output_dir"

# Initialize a variable to keep track of the timestamp
ts=""

# Loop until a unit test fails
while true; do
    # Generate a new timestamp in the format hour:minute:second
    ts=$(date "+%H:%M:%S")

    # Run pytest and redirect output to a file with the timestamp
    pytest > "$output_dir/out-${ts}.txt" 2>&1

    # Check the exit status of pytest
    if [ $? -ne 0 ]; then
        echo "An unit test failed. Exiting the loop."
        break
    else
        echo "Unit tests passed. Waiting before the next iteration."
        sleep 1
    fi
done
