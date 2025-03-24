#!/bin/bash
# Capture nodata value from the second argument
nodata=$1

# Set directory with LULC files
lulc_path="$(realpath "$(pwd)/data/input/lulc")"
# Output directory - save to parent directory with input LULC datasets
lulc_upd_compr_path="$(realpath "$(pwd)")/data/input/lulc"
# previous version - in subnested directory: lulc_upd_compr_path="lulc_pa"
inter_path="$(realpath "$(pwd)")/data/output/protected_areas"

# create these directories if they don't exist
mkdir -p "$lulc_upd_compr_path"

echo "LULC path: $lulc_path"

# List all LULC files in the directory
lulc_files=("$lulc_path"/*.tif)

# Set directory with PA files
pa_path="${inter_path}/pa_rasters"
pa_files=("$inter_path/$pa_path"/*.tif)
echo "Path to rasterised protected areas: $pa_files"

# Assign no-data values through the loop over LULC folder
for lulc_file in "$lulc_path"/*.tif; do
    # Print input and output filenames
    echo "Input filename: $lulc_file"
    filename=$(basename "$lulc_file")
    filename_without_extension="${filename%.*}"
    lulc_year="${filename_without_extension: -4}"

    # Validate extracted year
    if [[ "$lulc_year" =~ ^[0-9]{4}$ ]]; then
        echo "LULC year: $lulc_year"
    else
        echo "No valid year found in: $lulc_file ($lulc_year)"
        continue
    fi

    # Loop through each PA file
    for pa_file in "$pa_path"/*.tif; do
        echo "$pa_file"
        # Extract last four characters from PA file name (year)
        pa_year=$(basename "$pa_file" | cut -c 5-8)
        echo "PA year: $pa_year"

        # Check if LULC and PA files have matching years
        if [ "$lulc_year" = "$pa_year" ]; then
            # Process files
            lulc_upd_file="${lulc_file##*/}"
            lulc_upd_file="${lulc_upd_file%.tif}_upd"
            lulc_upd_file="$lulc_upd_path/${lulc_upd_file}.tif"
            echo "$lulc_upd_file"
            gdal_calc.py --overwrite --calc  "A+B" --format GTiff --type Int32 -A "$lulc_file" --A_band 1 -B "$pa_file" --outfile "$lulc_upd_file" --NoDataValue=$nodata 
            echo "Updated LULC is uploaded to: $lulc_upd_file"
    
            # Set paths for compressed updated LULC file
            lulc_upd_compr_file="${lulc_upd_file##*/}"
            lulc_upd_compr_file="${lulc_upd_compr_file%_upd.tif}"
            lulc_upd_compr_file="$lulc_upd_compr_path/${lulc_upd_compr_file##*/}_pa.tif"
            echo "Compressed LULC is uploaded to: $lulc_upd_compr_file"
            echo "----------------------------------"

            # Compress and set no data values
            gdal_translate -a_nodata $nodata -co COMPRESS=LZW -co TILED=YES "$lulc_upd_file" "$lulc_upd_compr_file"

            # Remove non-compressed updated LULC file
            rm "$lulc_upd_file"
          
            # Break the loop once a matching PA file is found
            break
        fi
    done
done
