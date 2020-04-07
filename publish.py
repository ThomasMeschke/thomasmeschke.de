#! python
import argparse
import time
from typing import List
import ftplib
import os
import sys


class FtpSession(object):
    def __init__(self, ftp_handle):
        self.ftp_handle = ftp_handle

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


class FtpHelper(object):
    def __init__(self, host: str, port: int, username: str, password: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password

    def connect(self) -> FtpSession:
        ftp = ftplib.FTP(self.host, self.username, self.password)
        return FtpSession(ftp)


def main() -> None:
    environment = get_env_from_args()
    print(f"=== Starting '{environment}' release ===")

    update_pubdate_file()
    file_list = collect_files_to_publish()

    try:
        sftp = start_sftp_session()
        base_dir = get_remote_base_dir_for(environment)
        publish_files_to(file_list, base_dir, sftp)
        sftp.close()
        print("=== DONE ===")
    except Exception as ex: 
        print(type(ex))
        print(str(ex))
        print("=== FAILED ===")
        sys.exit()


def get_env_from_args() -> str:
    parser = argparse.ArgumentParser()
    parser.add_argument("environment", choices=[
                        'dev', 'live'], help="the environment the page should be published to, dev or live")
    args = parser.parse_args()
    return args.environment


def update_pubdate_file() -> None:
    pubdate_file = open("pubdate.inf", "w")
    pubdate_file.write(time.strftime("%Y-%m-%d"))
    pubdate_file.close()


def collect_files_to_publish() -> List[str]:
    # expand the current folder into an absolute path
    root_dir = os.path.abspath('.')
    blacklist = ['.git', '.gitignore', '.idea', '.vscode', 'publish.py', 'README.md']
    files_to_publish = []
    for subdir, _, files in os.walk(root_dir):
        for file in files:
            full_path = os.path.join(subdir, file)
            ok = True
            for item in blacklist:
                ok = ok and item not in full_path
            if ok:
                full_path = full_path.replace(root_dir + "\\", '')
                full_path = full_path.replace('\\', '/')
                files_to_publish.append(full_path)
    return files_to_publish


def start_sftp_session() -> FtpSession:
    host = 'ftp.thomasmeschke.de'
    port = 21
    user = 'f012a02e'
    password = 'pBk38S4v8Nbfbz35'

    return FtpHelper(host, port, user, password).connect()


def get_remote_base_dir_for(environment: str) -> str:
    base_dir = ''
    if environment == 'dev':
        base_dir = base_dir + '/_dev'
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
            except Exception as exception:
                print(type(exception))
                print(str(exception))
                sys.exit()
        ftp_session.put_file(file_name, path_segments.pop(0))


if __name__ == "__main__":
    main()
