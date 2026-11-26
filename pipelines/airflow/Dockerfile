ARG DOCKERHUB_MIRROR=docker.io
FROM ${DOCKERHUB_MIRROR}/apache/airflow:2.10.5-python3.11

USER root
RUN rm -f /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources.disabled \
 && find /etc/apt/sources.list.d -type f ! -name 'debian.sources' -delete \
 && apt-get update \
 && apt-get install -y --no-install-recommends openjdk-17-jre-headless curl \
 && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    SPARK_JARS_DIR=/opt/spark-jars \
    SPARK_CONF_DIR=/opt/spark-conf

RUN mkdir -p /opt/spark-jars /checkpoints \
 && cd /opt/spark-jars \
 && for url in \
      https://repo1.maven.org/maven2/com/microsoft/sqlserver/mssql-jdbc/12.8.1.jre11/mssql-jdbc-12.8.1.jre11.jar \
      https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar \
      https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.3/spark-sql-kafka-0-10_2.12-3.5.3.jar \
      https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.3/spark-token-provider-kafka-0-10_2.12-3.5.3.jar \
      https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.4.1/kafka-clients-3.4.1.jar \
      https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar ; \
    do curl -fsSLO --retry 5 "$url"; done \
 && chown -R airflow:0 /checkpoints \
 && mkdir -p /opt/spark-conf \
 && printf '%s\n' \
      'spark.driver.extraClassPath   /opt/spark-jars/*' \
      'spark.executor.extraClassPath /opt/spark-jars/*' \
      'spark.sql.session.timeZone    UTC' \
      'spark.ui.showConsoleProgress  false' > /opt/spark-conf/spark-defaults.conf

USER airflow
COPY airflow/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
