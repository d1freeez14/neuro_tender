FROM ubuntu:22.04

RUN TZ=Asia/Almaty
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN apt update -y
RUN apt update -y --fix-missing 
RUN apt install -y wget unzip 

RUN apt install iproute2 -y

RUN apt update -y
RUN apt install curl -y
RUN apt install gpg -y
RUN apt install vim -y

RUN curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
RUN curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
RUN apt-get update -y

RUN apt install -y nvidia-container-toolkit
RUN curl -fsSL https://ollama.com/install.sh | sh

COPY entry.sh /opt/entry.sh
RUN chmod +x /opt/entry.sh

COPY Modelfile /opt/Modelfile

ENTRYPOINT /opt/entry.sh > /app/log/dgollama.log 2>&1
