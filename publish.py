#! python
import argparse
import time
from typing import List
import paramiko
import ftplib
import os
import sys
import traceback
import requests

USE_SFTP = False
FTP_LIVE_DIR = ''
FTP_DEV_SUBDIR = '/_dev'
FTP_HOST = 'ftp.thomasmeschke.de'
FTP_PORT = 21
FTP_USER = 'f012a02e'
FTP_PASSWORD = 'pBk38S4v8Nbfbz35'

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

LIVE_ADDRESS = "https://thomasmeschke.de/"
DEV_ADDRESS = "https://dev.thomasmeschke.de/"


class FtpSessionBase:
    def __init__(self, ftp_handle):
        if type(self) is FtpSessionBase:
            raise NotImplementedError('FtpSessionBase class cannot be instantiated directly')
        self.ftp_handle = ftp_handle
    
    def change_dir(self, directory_name) -> None: 
        # overwriten in the child classes
        pass

    def make_dir(self, directory_name) -> None: 
        # overwriten in the child classes
        pass

    def put_file(self, local_file: str, remote_file: str, callback=None, confirm_size=True) -> None:
        # overwriten in the child classes
        pass

    def close(self) -> None:
        # overwriten in the child classes
        pass


class FtpSession(FtpSessionBase):
    def __init__(self, ftp_handle):
        super().__init__(ftp_handle)

    def change_dir(self, directory_name: str) -> None:
        self.ftp_handle.cwd(directory_name)

    def make_dir(self, directory_name: str) -> None:
        self.ftp_handle.mkd(directory_name)

    def put_file(self, local_file: str, remote_file: str, callback=None, confirm_size=True) -> None:
        file = open(local_file, 'rb')
        self.ftp_handle.storbinary('STOR ' + remote_file, file)
        file.close()

    def close(self) -> None:
        self.ftp_handle.quit()


class SftpSession(FtpSessionBase):
    def __init__(self, ftp_handle):
        super().__init__(ftp_handle)

    def change_dir(self, directory_name: str) -> None:
        self.ftp_handle.chdir(directory_name)

    def make_dir(self, directory_name: str) -> None:
        self.ftp_handle.mkdir(directory_name)

    def put_file(self, local_file: str, remote_file: str, callback=None, confirm_size=True) -> None:
        self.ftp_handle.put(local_file, remote_file, callback, confirm_size)

    def close(self) -> None:
        self.ftp_handle.close()


class FtpSessionBuilder(object):
    
    def build_session(self, host: str, port: int, username: str, password: str) -> FtpSessionBase:
        if USE_SFTP: 
            return self.build_sftp_session(host, port, username, password)
        else:
            return self.build_ftp_session(host, username, password)

    def build_ftp_session(self, host: str, username: str, password: str) -> FtpSession:
        ftp = ftplib.FTP(host, username, password)
        return FtpSession(ftp)

    def build_sftp_session(self, host: str, port: int, username: str, password: str) -> SftpSession:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy)
        ssh.connect(host, port, username, password, banner_timeout=200)
        sftp = ssh.open_sftp()
        return SftpSession(sftp)


def main() -> None:
    args = get_args()
    environment = get_env_from_args(args)
    force_flag = get_force_flag_from_args(args)
    print(f"=== Starting '{environment}' release ===")
    try_download_pudate_file(environment)
    last_pubdate_timestamp = determine_last_pubdate_timestamp(environment, force_flag)
    update_pubdate_file(environment)
    file_list = collect_files_modified_after(last_pubdate_timestamp, environment)

    try:
        ftp_session = FtpSessionBuilder().build_session(FTP_HOST, FTP_PORT, FTP_USER, FTP_PASSWORD)
        base_dir = get_remote_base_dir_for(environment)
        publish_files_to(file_list, base_dir, ftp_session)
        ftp_session.close()
        print("=== DONE ===")
    except Exception: 
        print(traceback.format_exc())
        print("=== FAILED ===")
        sys.exit()


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("environment", choices=[
                        'dev', 'live'], help="the environment the page should be published to, dev or live")
    parser.add_argument("-f", "--force", action="store_true", help="ignore the last publish datetime and push all files")
    return parser.parse_args()


def get_env_from_args(args) -> str:
    return args.environment


def get_force_flag_from_args(args) -> bool:
    return args.force


def try_download_pudate_file(environment: str) -> None:
    file_name = 'pubdate_' + environment + '.inf'
    base_url = LIVE_ADDRESS if (environment == 'live') else DEV_ADDRESS
    file_url = base_url + file_name
    print("-> Try downloading '" + file_url + "'...")
    try:
        response = requests.get(file_url)
        pubdate_file = open(file_name, 'wb')
        pubdate_file.write(response.content)
        pubdate_file.close()
    except Exception:
        print("W: Could not download pubdate file!")


def determine_last_pubdate_timestamp(environment: str, force: bool) -> float:
    if force:
        print("W: Force flag was set, ignoring last pubdate!")
        return 0
    else: 
        return get_last_pubdate_from_pubdate_file(environment)

def get_last_pubdate_from_pubdate_file(environment: str) -> float:
    timestamp = 0
    try:
        pubdate_file = open(f"pubdate_{environment}.inf", "r")
        time_string = pubdate_file.read()
        pubdate_file.close()    
        time_struct = convert_time_string_to_struct_time(time_string)
        timestamp = convert_struct_time_to_timestamp(time_struct)
    except Exception:
        print(f"W: Could not read from pubdate info file, all files will be published!")
    return timestamp


def convert_time_string_to_struct_time(time_string: str) -> time.struct_time:
    return time.strptime(time_string, TIME_FORMAT)


def convert_struct_time_to_timestamp(time_struct: time.struct_time) -> float:
    return time.mktime(time_struct)


def update_pubdate_file(environment: str) -> None:
    pubdate_file = open(f"pubdate_{environment}.inf", "w")
    pubdate_file.write(time.strftime(TIME_FORMAT))
    pubdate_file.close()


def collect_files_modified_after(timestamp: float, environment: str) -> List[str]:
    root_dir = expand_current_folder_to_absolut_path()
    blocklist = ['.git', '.gitignore', '.idea', '.vscode', 'publish.py', 'README.md']
    other_env = 'dev' if (environment == 'live') else 'live'
    blocklist.append('pubdate_' + other_env + '.inf')
    files_to_publish = []
    for subdir, _, files in os.walk(root_dir):
        for file in files:
            full_path = os.path.join(subdir, file)
            ok = True
            for item in blocklist:
                ok = ok and item not in full_path
            ok = ok and file_changed_later_than(full_path, timestamp)
            if ok:
                full_path = full_path.replace(root_dir + "\\", '')
                full_path = full_path.replace('\\', '/')
                files_to_publish.append(full_path)
    return files_to_publish


def expand_current_folder_to_absolut_path() -> str:
    return os.path.abspath('.')


def file_changed_later_than(path: str, timestamp: float) -> bool:
    last_modified_timestamp = os.path.getmtime(path)
    return last_modified_timestamp > timestamp


def get_remote_base_dir_for(environment: str) -> str:
    base_dir = FTP_LIVE_DIR
    if environment == 'dev':
        base_dir = base_dir + FTP_DEV_SUBDIR
    return base_dir


def publish_files_to(file_list: List[str], base_dir: str, ftp_session: FtpSession) -> None:
    for file_name in file_list:
        ftp_session.change_dir(base_dir)
        print("-> " + file_name)
        
        path_segments = file_name.split("/")
        while len(path_segments) > 1:
            next_segment = path_segments.pop(0)
            try:
                ftp_session.change_dir(next_segment)
            except FileNotFoundError:
                ftp_session.make_dir(next_segment)
                ftp_session.change_dir(next_segment)
            except ftplib.error_perm:
                ftp_session.make_dir(next_segment)
                ftp_session.change_dir(next_segment)
            except Exception:
                print(traceback.format_exc())
                sys.exit()
        ftp_session.put_file(file_name, path_segments.pop(0))


if __name__ == "__main__":
    main()
