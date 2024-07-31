import random
import shutil
import requests
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from seleniumwire import webdriver  # 注意，这里使用的是 seleniumwire 而不是 selenium

from webdriver_manager.chrome import ChromeDriverManager

import os
import zipfile
import time
import tqdm
from pathlib import Path
from bs4 import BeautifulSoup

from utils import logger
from utils.agent import user_agent_list, proxy




class BaseDriver:

    def __init__(self) -> None:
        self.driver = None

    def chrome_options(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # 无头模式
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        # chrome_options.add_argument('--proxy-server=%s' % proxy)
        
        user_agent = random.choice(user_agent_list)
        chrome_options.add_argument(f'user-agent={user_agent}')

        return chrome_options

    def extract_with_progress(self,zip_path, extract_path):
        # 使用 tqdm 显示解压进度
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file in zip_ref.infolist():
                tqdm.write(f'Extracting: {file.filename}')
                zip_ref.extract(file, extract_path)
        time.sleep(1)
        shutil.rmtree(zip_path)

    def download_with_progress(self,url: str, dest: Path):        
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('content-length', 0))

        block_size = 1024  # 1 Kilobyte
        t = tqdm(total=total_size, unit='iB', unit_scale=True)

        with open(dest, 'wb') as file:
            for data in response.iter_content(block_size):
                t.update(len(data))
                file.write(data)
        t.close()

        if total_size != 0 and t.n != total_size:
            logger.error("ERROR: Something went wrong")
        time.sleep(1)
        
    def chrome_service(self, driver_path: str = 'drivers') -> Service:
        manager = ChromeDriverManager()
        os_type = manager.get_os_type()
        browser_type = manager.driver.get_browser_type()
        # driver_version = manager.driver.get_browser_version_from_os()
        executable_path = Path(driver_path, browser_type)
        
        if not os.path.exists(executable_path):
            executable_path.mkdir(parents=True, exist_ok=True)

        driver_url = manager.driver.get_driver_download_url(os_type=os_type)
        file_path, filename = os.path.split(driver_url)
        zip_path = executable_path.joinpath(filename)

        if not zip_path.is_file():
            self.download_with_progress(driver_url, zip_path)

        decompression_path = Path(os.path.splitext(zip_path)[0])
        executable_path = decompression_path.joinpath(decompression_path.as_posix().split('/')[-1], 'chromedriver')
        if not executable_path.is_file():
            self.extract_with_progress(zip_path=zip_path, extract_path=decompression_path)
            os.chmod(executable_path, 0o755)

        return Service(executable_path=executable_path)

    def get_driver(self) -> webdriver.Chrome:
        options = self.chrome_options()
        service = self.chrome_service()
        return webdriver.Chrome(service=service, options=options)
    
    def get_page(self, url: str, waitby_xpath: str = None) -> BeautifulSoup:
        if not (hasattr(self, 'driver') and self.driver):
            self.driver = self.get_driver()

        self.driver.get(url)

        if waitby_xpath:
            element = WebDriverWait(self.driver, 1000).until(
                EC.presence_of_element_located((By.XPATH, waitby_xpath))
            )
        else:
            element = self.driver._web_element_cls
        
        return BeautifulSoup(element.get_attribute('outerHTML'), 'html5lib')