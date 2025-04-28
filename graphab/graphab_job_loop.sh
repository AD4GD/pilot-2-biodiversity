#!/bin/bash

### INSTALLATION

# sudo snap install yq
# chmod +x graphab_job.sh (grant change permissions)
# cd ... (insert path)
# ./graphab_job.sh



### CONFIGURATION
# the parameters are called from the configuration YAML file



graphab_jar=$(yq e '.graphab_jar' "$CONFIG")
# case_study=$(yq e '.case_study' "$CONFIG")
sub=$(yq e '.sub.enabled' "$CONFIG")
sub_case_study=$(yq e '.sub.sub_case_study' "$CONFIG")
years=$(yq e '.years' "$CONFIG")
habitat=$(yq e '.habitat' "$CONFIG")
habitat_name=$(yq e '.habitat' "$CONFIG" | tr -d '*')
habitat_val=$(yq e ".$habitat" "$CONFIG")
nodata=$(yq e '.nodata' "$CONFIG")
minarea=$(yq e '.minarea' "$CONFIG")
maxdist=$(yq e '.maxdist' "$CONFIG")
maxdist_corr=$(yq e '.maxdist_corr' "$CONFIG")
merge=$(yq e '.merge' "$CONFIG")
#xms=$(yq e '.xms' "$CONFIG")
#xmx=$(yq e '.xmx' "$CONFIG")
#proc_num=$(yq e '.proc_num' "$CONFIG")
# mpi=$(yq e '.mpi' "$CONFIG")
con8=$(yq e '.con8' "$CONFIG") 
seq=$(yq e '.seq.enabled' "$CONFIG")
d_seq=$(yq e '.seq.d_seq' "$CONFIG")
p=$(yq e '.p' "$CONFIG")
beta=$(yq e '.beta' "$CONFIG")
beta_corridor=($(yq e '.beta_corridor[]' "$CONFIG"))
corridor_val_i=$(yq e '.corridor_val_i' "$CONFIG")
commands=($(yq e '.commands[]' "$CONFIG")) # extracts array from yaml
# NOTE: habitat_val  required to extract value from the anchor of habitat_name variable
# NOTE: it is not clear what is the scientific meaning if maxcost (distance, when creating a linkset) and threshold (distance, when creating a graph), are different
# NOTE: for now, they are defined as different parameters with the same default values
# TODO: to consider extra folder in config: config/$case_study/config123.yaml . But seems impossible because case_study is defined later

# TO SET UP EXTRA CONFIG FROM .ENV FILE
set -a
source .env
set +a

echo "CONFIGURATION CHECK"
echo "Configuration file: $CONFIG"
echo "Graphab JAR file: $graphab_jar"
echo "Case study name: $case_study"
echo "Sub-case studies considered: $sub"
([ "$sub" = "true" ] || [ "$sub" = "True" ]) && echo "Sub-case study name: $sub_case_study"
echo "Years to analyse: $years"
echo "Habitat name: $habitat_name"
echo "Habitat: $habitat"
echo "Habitat computed: $habitat_val"
echo "No-data value: $nodata"
echo "Minimum habitat area: $minarea"
echo "Maximum distance (indices): $maxdist"
echo "Maximum distance (corridors): $maxdist_corr"
echo "Merge habitats: $merge"
echo "Sequence of distance parameter: $seq"
echo "Distance parameter range: $d_seq"
echo "Beta value: $beta"
echo "Probability value: $p"
echo "Metric to calculate corridors: $corridor_val_i"
echo "Beta value(s) to compute corridors: ${beta_corridor[@]}"
echo "----------------"
echo "PERFORMANCE CONFIG:"
echo "MPI mode with Open MPI enabled: $mpi"
echo "8 neighbour pixels to compute: $con8"
echo "Initial heap size (RAM): $XMS"
echo "Maximum heap size (RAM): $XMX"
echo "Number of processors: $PROC_NUM"
echo "----------------"
echo "LIST OF COMMANDS: ${commands[@]}"
echo "----------------"

# define paths
# TODO - to consider /shared
lulc_path="data/$case_study/input/lulc/" 
if [ "$sub" = "true" ] || [ "$sub" = "True" ]; then
    impedance_path="data/$case_study/input/${sub_case_study}_impedance"
    output_dir="data/$case_study/output/$sub_case_study"
else
    impedance_path="data/$case_study/input/$impedance"
    output_dir="data/$case_study/output"
fi
# TODO - create output_dir if it is not created yet

# filter input datasets by year (if needed)
if [[ "$years" == "all" ]]; then
    lulc_files=("$lulc_path"/*.tif)
else
    lulc_files=()
    # check the year
    lulc_proc_files=("$lulc_path"/*.tif)
    for lulc_proc_file in "${lulc_proc_files[@]}"; do 
        # extract year (4 digits) from LULC filename
        lulc_numbers=$(echo "$lulc_proc_file" | grep -oP '\d{4}')    
        # if does not match, skip the file
        if echo "${years[@]}" | grep -wq "$lulc_numbers"; then
            # if matches add the file to the lulc_files array
            lulc_files+=("$lulc_proc_file")
        fi
    done
fi

echo "Input path (LULC): $lulc_path"
echo "Input LULC files:"
printf "%s\n" "${lulc_files[@]}"
echo "Input path (cost/impedance): $impedance_path"
echo "Output path: $output_dir"
echo "**********************************************************"

### PROCESSING

# to loop through each GeoTIFF file
for lulc_file in "${lulc_files[@]}"; do
    # to extract year from the LULC file name - 4 numbers
    lulc_numbers=$(echo "$lulc_file" | grep -oP '\d{4}')

    # to print names of files and years
    echo "LULC File: $lulc_file"
    echo "Extracted Year: $lulc_numbers"

    # the statement to find the matching impedance file for the particular lulc_file
    impedance_file="${impedance_path}/impedance_${lulc_file#$lulc_path/}"

    # the statement to find the matching impedance file for the particular lulc_file (lulc is not rewritten by protected areas)
    # Remove file extension from lulc_file
    lulc_file_no_ext="${impedance_file%.tif}"
    # Construct impedance file path with "_pa" suffix
    impedance_pa_file="${lulc_file_no_ext}_pa.tif"
    impedance=$impedance_file # choose from $impedance_file and $impedance_pa_file (without or with pa considered)

    echo "Current directory: $(pwd)"
    echo "Impedance File: $impedance"

    # create a directory for outputs
    mkdir -p $output_dir

    # to find corresponding Graphab project name based on the extracted year
    if [[ "$lulc_path/lulc_${lulc_numbers}"?*.tif == "$lulc_path/lulc_${lulc_numbers}".tif ]]; then
        test_loop="con_${lulc_numbers}"
        
    else
        # extract the extra symbols from the filename
        base_name=$(basename "$lulc_file" .tif)
        extra_symbols="${base_name#lulc_${lulc_numbers}}"
        test_loop="con_${lulc_numbers}_${extra_symbols}"
        echo "Project name: $test_loop"
    fi
    
    test_loop_xml="$output_dir/$test_loop/$test_loop.xml"
    test_capacity="patches_capa_${lulc_numbers}.csv"
   
    # to check if the impedance file exists before proceeding
	# to include customised capacity of patch use "--capa file=$test_capacity id=Id capacity=capacity"

	# listing available commands
    if [ -f "$impedance" ]; then
        ## CONSTRUCT COMMANDS
	    # 0.1 create project
	    proj="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar -proc $PROC_NUM --create $test_loop $lulc_file nodata=$nodata dir=$output_dir"
        # It is also possible to add --graph name=name

        # 0.2 define habitat and calculate linkset
        # if sequence of distance values defined, use it
        if [[ "$d_seq" == "true" || "$d_seq" == "True" ]]; then
            habitat_linkset="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar --project $test_loop_xml --habitat name=$habitat_name codes=$habitat_val minarea=$minarea --linkset distance=cost name=cost_${maxdist} maxcost=$maxdist extcost=$impedance --graph threshold=$d_seq"
        else
            habitat_linkset="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar --project $test_loop_xml --habitat name=$habitat_name codes=$habitat_val minarea=$minarea --linkset distance=cost name=cost_${maxdist} maxcost=$maxdist extcost=$impedance --graph threshold=$maxdist"
        fi

        # 0.3 show (inspect) the created project
        show="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar --project $test_loop_xml --show"

        ## 1. GLOB indices (parameterised)
        if [[ "$d_seq" == "true" || "$d_seq" == "True" ]]; then
            glob_pc="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar --project $test_loop_xml --gmetric PC resfile=glob_PC_${lulc_numbers}.txt d=$d_seq p=$p beta=$beta"
            glob_ec="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar --project $test_loop_xml --gmetric EC resfile=glob_EC_${lulc_numbers}.txt d=$d_seq p=$p beta=$beta"
	    else
            glob_pc="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar --project $test_loop_xml --gmetric PC resfile=glob_PC_${lulc_numbers}.txt d=$maxdist p=$p beta=$beta"
            glob_ec="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar --project $test_loop_xml --gmetric EC resfile=glob_EC_${lulc_numbers}.txt d=$maxdist p=$p beta=$beta"
        fi
	
	    ## 2. GLOB indices (non-parameterised, within project can vary only by graph)
	    glob_iic="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar --project $test_loop_xml --gmetric IIC resfile=glob_IIC_${lulc_numbers}.txt"
	    glob_nc="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar --project $test_loop_xml --gmetric NC resfile=glob_NC_${lulc_numbers}.txt"

        # 3. LOCAL indices
        if [[ "$d_seq" == "true" || "$d_seq" == "True" ]]; then
            loc_if="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar -proc $PROC_NUM --project $test_loop_xml --lmetric F d=$d_seq p=$p beta=$beta"
            loc_cf="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar -proc $PROC_NUM --project $test_loop_xml --lmetric CF d=$d_seq p=$p beta=$beta"
            loc_bc="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar -proc $PROC_NUM --project $test_loop_xml --lmetric BC d=$d_seq p=$p beta=$beta"
        else
            loc_if="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar -proc $PROC_NUM --project $test_loop_xml --lmetric F d=$maxdist p=$p beta=$beta"
            loc_cf="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar -proc $PROC_NUM --project $test_loop_xml --lmetric CF d=$maxdist p=$p beta=$beta"
            loc_bc="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar -proc $PROC_NUM --project $test_loop_xml --lmetric BC d=$maxdist p=$p beta=$beta"
        fi

        # 4.DELTA indices 
        # GLobal indices in delta mode (for each patch)
        # TODO - to add condition on -mpi flag
        if [[ "$d_seq" == "true" || "$d_seq" == "True" ]]; then
            d_iic="mpirun java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar -proc $PROC_NUM -mpi --project $test_loop_xml --delta IIC d=$d_seq p=$p beta=$beta obj=patch"
            d_pc="mpirun java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar -proc $PROC_NUM -mpi --project $test_loop_xml --delta PC d=$d_seq p=$p beta=$beta obj=patch"
        else
            d_iic="mpirun java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar -proc $PROC_NUM -mpi --project $test_loop_xml --delta IIC d=$maxdist p=$p beta=$beta obj=patch"
            d_pc="mpirun java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar -proc $PROC_NUM -mpi --project $test_loop_xml --delta PC d=$maxdist p=$p beta=$beta obj=patch"
        fi
       
        # 5. CORRIDORS

        # BY BETA VALUE
        # create the command array for each beta value
        upd_commands=()
        for beta_corridor_val in "${beta_corridor[@]}"; do
            var_name="corridors_by_beta_${beta_corridor_val//./_}" #replace . with _
            # build the command string for each beta value (ensure no extra quotes or parentheses)
            command="java -Xms${XMS} -Xmx${XMX} -jar $graphab_jar -proc $PROC_NUM --project $test_loop_xml --corridor maxcost=$maxdist_corr format=raster beta=$beta_corridor_val d=$maxdist_corr p=$p"
            declare -g $var_name="$command"          
            echo "Generated variable: $var_name -> ${!var_name}"
        done

	    # TODO - to store names of local metrics in corridors command for 'var' placeholder
	    # TODO - to try not define project each time for a new command (might work automatically)

        # replace commands
        for cmd in "${commands[@]}"; do
            if [[ "$cmd" == "corridors_by_beta" ]]; then
                for beta_corridor_val in "${beta_corridor[@]}"; do
                    var_name="corridors_by_beta_${beta_corridor_val//./_}"  # Ensure same name format
                    upd_commands+=("$var_name")  # Store variable name, not raw command
                done
            else
                upd_commands+=("$cmd")  # Keep original commands
            fi
        done

        # Debug: Show the updated list of commands (variable names)
        echo "Updated list of commands: ${upd_commands[@]}"

        for cmd in "${upd_commands[@]}"; do
            echo "RUNNING COMMAND: $cmd"
            eval ${!cmd} # indirect variable expansion
        done
         
        # NOTE: do not try to run $cmd without eval and indirect var expansion - commands are not recognised in this case!

        # find and rename all corridor files
        find "$output_dir/$test_loop/" -type f -name "*corridor*.tif" 2>/dev/null | \
        while IFS= read -r generated_file; do
            # exclude files that contain the case_study name
            filename=$(basename "$generated_file")
            if [[ "$filename" != *"$case_study"* ]]; then
                if [[ -n "$generated_file" ]]; then
                    # rename depending on whether sub case study is defined
                    if [ "$sub" = "true" ] || [ "$sub" = "True" ]; then
                        new_name="${case_study}_${sub_case_study}_${lulc_numbers}_$(basename "$generated_file")"
                    else
                        new_name="${case_study}_${lulc_numbers}_$(basename "$generated_file")"
                    fi

                    mv "$generated_file" "$output_dir/$test_loop/$new_name"
                    echo "Renamed corridors file: $(basename "$generated_file") -> $new_name"
                    echo "******************"
                fi
            else
                echo "Skipping file as it contains $case_study: $generated_file"
                echo "******************"
            fi
        done

        echo "******************"

        # check the exit status of the last command
        if [ $? -eq 0 ]; then
            echo "Command for $lulc_file completed successfully."
        else
            echo "Error: command for $lulc_file encountered an issue."
        fi

    else
        echo "Error: Impedance file $impedance_file not found for $lulc_file"
    fi

    echo "**********************************************************"
done