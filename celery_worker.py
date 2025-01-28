from app import celery

celery.worker_main(argv=['worker', '--loglevel=info'])
