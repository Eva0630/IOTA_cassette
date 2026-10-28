FROM eclipse-temurin:8-jre

ENV JAVA_OPTIONS="-XX:+UnlockExperimentalVMOptions -XX:+DisableAttachMechanism -XX:InitiatingHeapOccupancyPercent=60 -XX:G1MaxNewSizePercent=75 -XX:MaxGCPauseMillis=10000 -XX:+UseG1GC" \
    JAVA_MIN_MEMORY=2G \
    JAVA_MAX_MEMORY=4G \
    DOCKER_IRI_JAR_PATH=/iri/target \
    DOCKER_IRI_JAR_FILE=iri*.jar \
    DOCKER_IRI_REMOTE_LIMIT_API="interruptAttachToTangle, attachToTangle, addNeighbors, removeNeighbors, getNeighbors" \
    DOCKER_IRI_MONITORING_API_PORT_ENABLE=0 \
    DOCKER_IRI_MONITORING_API_PORT_DESTINATION=14265 \
    DOCKER_IRI_REMOTE=true \
    DOCKER_JAVA_NET_PREFER_IPV4_STACK=true

COPY iri-1.8.6-RELEASE.jar /iri/target/iri-1.8.6-RELEASE.jar
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /iri/data
ENTRYPOINT ["/entrypoint.sh"]
