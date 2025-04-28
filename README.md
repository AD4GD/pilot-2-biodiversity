<p align="center">
<img alt="A schematic diagram of the dataflow in pilot 2" src="https://github.com/user-attachments/assets/68a1d122-1d66-4c5f-a154-7063aeb419be">
</p>

This repository is dedicated to the Pilot 2 of the AD4GD project. <br />
- ***Preprocessing*** sub-repository is focused on Data4Land tool which enriches the input raster land-use/land-cover (LULC) data with OpenStreetMap database. Protected areas from World Database on Protected areas are integrated into preprocessing workflow to consider their importance for connecting habitats. <br />
- ***Graphab*** sub-repository contains containerised Graphab Java application (Deliverables 6.1, section 6.7) and postprocessing workflow to be deployed on the Kubernetes cluster connected with Minio object storage to ensure consistency of environment and to allow the workflow to be run reliably either on a users machine or as an open service module . <br />
- ***GBIF*** sub-repository is focused on the analysis of existing GBIF and IUCN data (quering, access, provenance and quality of records), corresponding with the Deliverables 6.1 (section 4.6.3, GBIF ingestion). The actual integration of GBIF data with other sources for target species is analysed [here](https://github.com/AD4GD/pilot-2-gbif-iucn). <br />

## Acknowledgements

The work has been co-funded by the European Union and the United Kingdom under the 
Horizon Europe [AD4GD Project](https://www.ogc.org/initiatives/ad4gd/).
