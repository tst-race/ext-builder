#
# Copyright 2023 Two Six Technologies
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# 

FROM ubuntu:20.04

# Install base utilities (to handle installs)
RUN apt-get -y update && \
    apt-get install -y \
        lsb-release \
        openjdk-8-jdk \
        software-properties-common \
        wget \
        unzip

# Install Android NDK
ARG ANDROID_TOOLS_VERSION=6609375
RUN mkdir -p /opt/android/cmdline-tools && \
    cd /opt/android/cmdline-tools && \
    wget https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_TOOLS_VERSION}_latest.zip && \
    unzip commandlinetools-*.zip && \
    rm commandlinetools-*.zip
ARG ANDROID_NDK_VERSION=23.2.8568313
RUN yes | /opt/android/cmdline-tools/tools/bin/sdkmanager --licenses && \
    /opt/android/cmdline-tools/tools/bin/sdkmanager --install "ndk;${ANDROID_NDK_VERSION}" && \
    ln -s /opt/android/ndk/${ANDROID_NDK_VERSION} /opt/android/ndk/default

# Add additional apt repositories
RUN \
    # LLVM
    apt-key adv --fetch-keys https://apt.llvm.org/llvm-snapshot.gpg.key && \
    add-apt-repository "deb http://apt.llvm.org/$(lsb_release -cs)/ llvm-toolchain-$(lsb_release -cs)-15 main" && \
    # CMake
    wget -O - https://apt.kitware.com/keys/kitware-archive-latest.asc 2>/dev/null | apt-key add - && \
    add-apt-repository "deb https://apt.kitware.com/ubuntu/ $(lsb_release -cs) main"

# Install apt packages
RUN apt-get -y update && \
    apt-get install -y --no-install-recommends \
        clang-15=1:15.0* \
        cmake=3.23.* \
        cmake-data=3.23.* \
        libclang-rt-15-dev=1:15.0* \
        llvm-15=1:15.0* \
        make=4.2.* \
        python3=3.8.* \
        wget=1.20.* && \
    update-alternatives --install /usr/bin/clang clang /usr/bin/clang-15 1 && \
    update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-15 1

# Install cross-compilation packages
ARG TARGETPLATFORM
RUN case ${TARGETPLATFORM} in \
        "linux/amd64") CROSS_ARCH=aarch64 ;; \
        "linux/arm64") CROSS_ARCH=x86-64  ;; \
    esac && \
    apt-get -y update && \
    apt-get install -y \
        g++-${CROSS_ARCH}-linux-gnu=4:9.3.*

# Setup multiarch repositories
RUN case ${TARGETPLATFORM} in \
        "linux/amd64") THIS_ARCH=amd64; CROSS_ARCH=arm64 ;; \
        "linux/arm64") THIS_ARCH=arm64; CROSS_ARCH=amd64 ;; \
    esac && \
    dpkg --add-architecture ${CROSS_ARCH} && \
    sed -i -e "s/deb http/deb [arch=$THIS_ARCH] http/" /etc/apt/sources.list
COPY docker-image/${TARGETPLATFORM}/cross-compile-sources.list /etc/apt/sources.list.d/cross-compile-sources.list

ENV ANDROID_NDK=/opt/android/ndk/default \
    MIN_SDK_VERSION=29 \
    CC=clang \
    CXX=clang++ \
    PATH=${PATH}:/opt/android/cmdline-tools/tools/bin

COPY docker-image/android-*.toolchain.cmake /opt/android/ndk/default/
COPY race_ext_builder.py /usr/lib/python3.8/
