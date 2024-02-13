FROM --platform=linux/amd64 node:20

RUN apt-get update \
    && apt-get install -y less vim

# PythonのバージョンはAWSのAmazon Linux 2023に合わせるので、3.9.16に変更した
RUN cd /opt \
    && curl -q "https://www.python.org/ftp/python/3.9.16/Python-3.9.16.tgz" -o Python-3.9.16.tgz \
    && tar -xzf Python-3.9.16.tgz \
    && cd Python-3.9.16 \
    && ./configure --enable-optimizations \
    && make install

RUN cd /opt \
    && curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install

# Session Manager Pluginのインストール EC2と簡単に接続できるようなもの
RUN curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb" -o "session-manager-plugin.deb" \
    && dpkg -i session-manager-plugin.deb \
    && rm session-manager-plugin.deb

RUN python3 -m pip install --upgrade pip

RUN npm install -g aws-cdk

# clean up unnecessary files
RUN rm -rf /opt/*

# Make command line prettier...
RUN echo "alias ls='ls --color=auto'" >> /root/.bashrc
RUN echo "PS1='${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u@aws-cdk\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '" >> /root/.bashrc

WORKDIR /root/work
CMD ["/bin/bash"]
