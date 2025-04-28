# syntax=docker/dockerfile:1
FROM ghcr.io/osgeo/gdal:ubuntu-small-latest AS base
# alternative if small docker image does not work:
# FROM ghcr.io/osgeo/gdal:ubuntu-full-latest AS base

# specify working directory
WORKDIR /src

# install dependencies and Java
RUN apt-get update && apt-get install -y \
    openjdk-11-jre \
    bash \
    python3 \
    python3-pip \
    python3-venv

RUN apt-get update --fix-missing
RUN apt-get install --fix-missing -y python3 python3-pip python3-venv

# download and install yq (latest)
RUN curl -sSL https://github.com/mikefarah/yq/releases/download/v4.15.1/yq_linux_amd64 -o /usr/bin/yq \
    && chmod +x /usr/bin/yq

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# copy to container
COPY requirements.txt .
# install packages from requirements
RUN pip install -r requirements.txt

COPY . .

# to keep container alive
CMD ["python3" , "main.py" , "cat_aggr_buf_390m_test" , "forest,shrubland,woody,herbaceous,aquatic"]

# set the entrypoint - just open bash
# ENTRYPOINT ["/bin/bash"]