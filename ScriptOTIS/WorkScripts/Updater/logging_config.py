# logging_config.py 
LOGGING_CONFIG = {
    "log_level": "DEBUG",
    "log_format": "%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S",
    "log_to_console": True,
    "log_to_file": True,
    "log_directory": "application_logs",
    "log_filename": "server_updater.log",
    "max_file_size": 5242880,  # 5 MB
    "backup_count": 10,
    "encoding": "utf-8",
    "separate_module_logs": False,
}
