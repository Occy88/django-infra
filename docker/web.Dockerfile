FROM di_base_python

ENTRYPOINT ["/home/app/web/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application","--log-level","info", "--access-logfile", "-","--limit-request-line","8190", "--workers", "4", "--bind", ":8000"]
