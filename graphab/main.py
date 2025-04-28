# Use this script to runs all other scripts in sequence 
import os
import sys
from utils import Timer
import argparse

os.makedirs('logs', exist_ok=True)
print("Logs are redirected to /logs")
sys.stdout = open('logs/main.log', 'w') #to log
sys.stderr = sys.stdout

if __name__ == "__main__":
    """'
    # Example usage: 
    python3 main.py {casestudy} {habitat}
    python3 main.py cat_aggr_buf_30m_test forest,shrubland,woody,herbaceous,aquatic
    """
    parser = argparse.ArgumentParser(description="Run all scripts in sequence for a given case study and habitat.")
    parser.add_argument("case_study", type=str, help="Case study identifier")
    parser.add_argument("habitat", type=str, help="Habitat identifier")
    args = parser.parse_args()

    case_study = args.case_study
    habitat = args.habitat

    # run minio-reader.py in this directory
    bucket_name = "pilot.2.graphab"
    input_dir = "data/cat_aggr_buf_390m_test"
    ext_bucket_name = "pilot2bioconn" # to fetch data from other sources (MiraMon outputs, for example)

    timer = Timer()

    # 0. minio-reader
    print("READING MinIO...")
    timer.start()
    os.system(f"python3 minio_reader.py --bucket_name {bucket_name} --ext_bucket_name {ext_bucket_name} --skip-existing-files --verbose")
    timer.print_elapsed()
    
    # 1. impedance_csv2tif.py
    print("RUNNING impedance_csv2tif.py...")
    timer.start()
    os.system(f"python3 impedance_csv2tif.py {case_study} {habitat}")
    timer.print_elapsed()

    print ("*" * 60)
    print ("*" * 60)
    print ("*" * 60)

    # 2. graphab
    print("RUNNING Graphab wrapper...")
    timer.start()
    os.system(f"./graphab_wrapper.sh {case_study}")
    timer.print_elapsed()

    print ("*" * 60)
    print ("*" * 60)
    print ("*" * 60)

    # 3. glob indices
    print("RUNNING glob_indices.py...")
    timer.start()
    os.system(f"python3 ./glob_indices.py {case_study}")
    timer.print_elapsed()


    print ("*" * 60)
    print ("*" * 60)
    print ("*" * 60)
    
    # 4. gpkg -> tif
    print("RUNNING join_gpkg2tif.py...")
    timer.start()
    os.system(f"python3 ./join_gpkg2tif.py {case_study}")
    timer.print_elapsed()

    print ("*" * 60)
    print ("*" * 60)
    print ("*" * 60)
    
    # 5. postproc
    print("RUNNING postproc.py...")
    timer.start()
    os.system(f"python3 ./postproc.py {case_study}")
    timer.print_elapsed()
    print ("*" * 60)
    print("PROCESSING COMPLETED!")

    # 6. run minio-uploader.py in this directory
    print("UPDATING MinIO...")
    bucket_name = "pilot.2.graphab"  # Replace with your bucket name
    timer.start()
    os.system(f"python3 ./minio_uploader.py --bucket_name {bucket_name} --input_dir {input_dir}")
    timer.print_elapsed()

    print ("*" * 60)
    timer.print_total_elapsed()
    del timer

    # run preprocessing scripts




