# syntax=docker/dockerfile:1


FROM python:3.11
ENV PYTHONUNBUFFERED=1


# install nginx
# RUN apt-get update && apt-get install nginx vim -y --no-install-recommends
# COPY server_configs/dev/nginx.conf /etc/nginx/sites-available/default
# RUN ln -sf /dev/stdout /var/log/nginx/access.log \
#     && ln -sf /dev/stderr /var/log/nginx/error.log

# EXPOSE 8080
# RUN service nginx restart



# copy source and install dependencies
WORKDIR /code
COPY . /code/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# start serverd
EXPOSE 8000
#CMD ["gunicorn", "--preload", "--bind", "0.0.0.0:8000", "--keep-alive", "180", "--workers", "3", "--worker-connections", "1000", "aapooncontact.wsgi:application"]
CMD ["gunicorn", "--preload", "--bind", "0.0.0.0:8000", "--keep-alive", "30", "--workers", "3", "--log-level", "debug", "--access-logfile", "-", "--log-file", "-", "--timeout", "90", "circle_service.wsgi:application"]
#CMD ["python", "gcrmserver/bin/manage.py", "runserver", "0.0.0.0:8000"]
