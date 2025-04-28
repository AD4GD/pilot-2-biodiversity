#!/bin/bash

# This wrapper runs Graphab job multiple times, looping over the multiple case studies and configurations

mkdir -p logs  # make sure logs directory exists
exec > logs/graphab.log 2>&1 # to log
echo "Logs are redirected to logs/"  # redirect both stdout and stderr to a log file


#FOR MPI
# Create a new user (if needed)
# useradd -m mpiuser2

# Switch to that user
# su - mpiuser2

# Print the current user
# current_user=$(whoami)
# echo -e "The current user is: \033[36m$current_user\033[0m"

### CAPTURE TIME
# global variable to store start time
start_time=0
# function to start measuring time
start_timer() {
    start_time=$(date +%s)  # capture current time in seconds
    echo -e "\033[34mTimer started at $(date)\033[0m"
    echo "------------------------------------------------"
}

# function to stop measuring time
stop_timer() {
    if [ $start_time -eq 0 ]; then
        echo -e "\033[31mError: Timer was never started!\033[0m"
        return
    fi
    end_time=$(date +%s)  # capture end time in seconds
    elapsed_time=$((end_time - start_time))  # calculate elapsed time
    echo -e "\033[32mElapsed time: ${elapsed_time} seconds!\033[0m \033[32m\033[0m"
    echo "------------------------------------------------"
}
start_timer


### PROCESSING
# ensure at least one argument given
if [ "$#" -eq 0 ]; then
    echo "Usage: $0 case1,case2,case3"
    exit 1
fi

# convert comma-separated case studies into an array
IFS=',' read -r -a case_studies <<< "$1"

echo "**************************************************"
echo -e "\033[34;47mList of case studies:\033[0m" 
printf "%s\n" "${case_studies[@]}"
echo "**************************************************"
echo "**************************************************"

for case_study in "${case_studies[@]}"; do
    echo -e "\033[34;47mRunning GRAPHAB for case study: $case_study\033[0m"
    
    # find all configuration files for the current case study
    config_files=($(find "config/$case_study/" -maxdepth 1 -type f -name "*.yaml" ! -name "*multi*.yaml"))
    
    # check if any YAML files were found
    if [[ ${#config_files[@]} -eq 0 ]]; then
        echo "No configuration files found in config/$case_study/"
        continue
    fi

    echo "**************************************************"
    echo -e "\033[34;47mConfiguration files for $case_study:\033[0m"

    printf '%s\n' "${config_files[@]}"
    echo "**************************************************"

    for config in "${config_files[@]}"; do
        echo -e "\033[34;47mRunning GRAPHAB with config: $config\033[0m"
        CONFIG="$config" case_study="$case_study" bash ./graphab_job_loop.sh
        printf "%s\n" "$(printf '********************************************************************************\n%.0s' {1..5})"
    done

done

### CAPTURE TIME
stop_timer
