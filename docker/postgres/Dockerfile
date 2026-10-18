# PostGIS plus pgvector. This postgis tag is built on Debian bullseye, whose
# PGDG packages now live on apt-archive.postgresql.org.
FROM postgis/postgis:15-3.3
RUN sed -i 's|apt.postgresql.org/pub/repos/apt|apt-archive.postgresql.org/pub/repos/apt|' \
        /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-15-pgvector \
    && rm -rf /var/lib/apt/lists/*
