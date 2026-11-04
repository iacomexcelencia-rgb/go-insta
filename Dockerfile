FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
WORKDIR /app
RUN pip install --no-cache-dir gunicorn==26.2.0
COPY --chmod=644 *.py ./
COPY go-public ./go-public
USER 10002:10002
EXPOSE 8766
CMD ["gunicorn","application:configured_app()","--bind","0.0.0.0:8766","--workers","1","--threads","4","--timeout","180","--worker-tmp-dir","/tmp","--error-logfile","-"]
