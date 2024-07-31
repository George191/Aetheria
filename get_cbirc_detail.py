import os
import json
from pathlib import Path
from typing import List
import pandas as pd
import requests
import zipfile
import selenium
from tqdm import tqdm
import time
# from selenium import webdriver
from seleniumwire import webdriver  # 注意，这里使用的是 seleniumwire 而不是 selenium
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.chrome import ChromeDriverManager

from bs4 import BeautifulSoup, Tag



class CbircCrawler:

    def __init__(self) -> None:
        service = self.chrome_service()
        chrome_options = self.chrome_options()
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.url = 'https://www.cbirc.gov.cn'
        self.number = 0


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
            print("ERROR: Something went wrong")
        time.sleep(1)

    def extract_with_progress(self,zip_path, extract_path):
        # 使用 tqdm 显示解压进度
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file in zip_ref.infolist():
                tqdm.write(f'Extracting: {file.filename}')
                zip_ref.extract(file, extract_path)
        time.sleep(1)
        
    def chrome_service(self, driver_path: str = 'drivers'):

        manager = ChromeDriverManager()
        os_type = manager.get_os_type()
        browser_type = manager.driver.get_browser_type()
        # driver_version = manager.driver.get_browser_version_from_os()
        executable_path = Path(driver_path, browser_type)
        
        if not os.path.exists(executable_path):
            executable_path.mkdir(parents=True, exist_ok=True)

        driver_url = manager.driver.get_driver_download_url(os_type=os_type)
        filename = driver_url.split('/')[-1]
        zip_path = executable_path.joinpath(filename)

        if not zip_path.is_file():
            self.download_with_progress(driver_url, zip_path)

        decompression_path = Path(os.path.splitext(zip_path)[0])
        executable_path = decompression_path.joinpath(decompression_path.as_posix().split('/')[-1], 'chromedriver')
        if not executable_path.is_file():
            self.extract_with_progress(zip_path=zip_path, extract_path=decompression_path)
            os.chmod(executable_path, 0o755)

        return Service(executable_path=executable_path)

    def chrome_options(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # 无头模式
        chrome_options.add_argument('--disable-gpu')
        return chrome_options

    def get_page(self, url: str, waitby_xpath: str = None):
        self.driver.get(url)
        if waitby_xpath:
            WebDriverWait(self.driver, 1000).until(
                EC.presence_of_element_located((By.XPATH, waitby_xpath))
            )
        return self.driver.page_source
        # return BeautifulSoup(self.driver.page_source, 'html5lib')
    
    def get_more(self, page: BeautifulSoup):
        result_set = page.find_all('a', {'class': 'caidan-right-zhengwuxinxi-list-more'})
        for result in result_set[1:]:
            yield result

    def parse_list(self, tag: Tag):
        itemsubPName = tag['href'].split('itemsubPName=')[1].split('&')[0]
        itemName = tag['href'].split('itemName=')[1].split('&')[0]
        href = tag['href']
        return itemsubPName, itemName, href
    
    def parse_sub_list(self, page: BeautifulSoup):
        row: List[BeautifulSoup] = page.find_all('div', {'class': 'panel-row ng-scope', 'ng-repeat': 'x in data'})
        for tag in row:
            title = tag.select_one('.title a')
            date = tag.select_one('.date')
            href = title['href']
            context = title.get_text()
            date = date.get_text()
            yield context, date, href

    def parse_table(self, page: BeautifulSoup):
        wenzhang_title = page.find('div', {'class': 'wenzhang-title'})
        title = ''
        if wenzhang_title:
            title = wenzhang_title.get_text(strip=True)

        content = page.find('div', {'id': 'wenzhang-content'})
        table = content.find('table')
        mapping = {}
        if not table:
            rows_p = content.find_all('p')
            row = [row.get_text(strip=True) for row in rows_p]
            mapping['content'] = row
        else:
            result = {}
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) == 2:
                    header = cells[0].get_text(strip=True)
                    content_paragraphs = [p.get_text(strip=True) for p in cells[1].find_all('p')]
                    result[header] = content_paragraphs
            mapping['content'] = result
        mapping['title'] = title
        return mapping
    
    def parse_page(self, page: BeautifulSoup):
        pager = page.find('div', {'ng-show': 'data.length!=0', 'pager2': True})
        page_num, max_page = pager.find('div', {'class': 'ng-binding', 'ng-show': False}).get_text(strip=True).split('/')

        page_num = int(page_num)
        max_page = int(max_page)

        t = tqdm(total=max_page, unit='it', unit_scale=True)

        WebDriverWait(self.driver, 1000).until(
            lambda x: x.find_element(by=By.XPATH, value="//*[@class='panel-row ng-scope' and @ng-repeat='x in data']")
        )

        yield self.parse_detail(page)
        t.update()

        while page_num < max_page:
            try:
                initial_requests_count = len(self.driver.requests)

                next_page_xpath = "//a[@ng-click='pager.next()']"
                prev_page_xpath = "//a[@ng-click='pager.prev()']"
                
                
                next_page_btn = WebDriverWait(self.driver, 1000).until(
                    EC.element_to_be_clickable((By.XPATH, next_page_xpath))
                )
                prev_page_btn = WebDriverWait(self.driver, 1000).until(
                    EC.element_to_be_clickable((By.XPATH, prev_page_xpath))
                )
                next_page_btn.click()
                time.sleep(1)

                WebDriverWait(self.driver, 10).until(lambda d: len(d.requests) > initial_requests_count)
                new_requests = self.driver.requests[initial_requests_count:]
                for request in new_requests:
                    if f"DocInfo/SelectDocByItemIdAndChild" in request.url:
                        if (hasattr(request.response, 'status_code') and request.response.status_code == 200) or request.url.endswith('.json'):
                            
                            WebDriverWait(self.driver, 1000).until(
                                lambda x: x.find_element(by=By.XPATH, value="//*[@class='panel-row ng-scope' and @ng-repeat='x in data']")
                            )
                            interface_data = pd.DataFrame(json.loads(request.response.body.decode('utf-8'))['data']['rows'])
                            page = BeautifulSoup(self.driver.page_source, 'html5lib')

                            selenium_data = self.parse_detail(page)
                            result = pd.merge(left=selenium_data, right=interface_data, left_on='context', right_on='docSubtitle')
                            yield result
                            page_num += 1
                            t.update()
                            time.sleep(1)

                        else:
                            prev_page_btn.click()
                            tqdm.write(f'Error: {request.url}')
                            time.sleep(60)

            except selenium.common.exceptions.TimeoutException as e:
                prev_page_btn.click()
                tqdm.write(f'Error: timeout. {e}')
                time.sleep(60)

    def parse_detail(self, page: BeautifulSoup):
        row_pool = pd.DataFrame()

        for context, date, href in self.parse_sub_list(page):
            res_row = {'context': context, 'date': date, 'href': href}
            row_pool = row_pool._append(res_row, ignore_index=True)
        return row_pool

    def get_table(self, url: str):
        waitby_xpath = '//div[@id="wenzhang-content"]//p'
        page = self.get_page(self.url + '/cn/view/pages/' + url, waitby_xpath=waitby_xpath)
        return page
        # return self.parse_table(page)

    def main(self, data_path: str):
        # 223.70.159.255
        data = pd.read_json(data_path)

        tqdm.write(f'Total {data.shape[0]} records')
        t = tqdm(total=data.shape[0], unit='it', unit_scale=True)

        result = pd.DataFrame()

        mapping = {}
        for _, row in data.iterrows():
            url = row['href']
            tqdm.write(url)
            context = self.get_table(url)
            mapping['docId'] = row.docId
            mapping['context'] = context

            result = result._append(mapping, ignore_index=True)
            t.update()

        result.to_json(data_path.replace('list', 'source'), indent=4, orient='records', force_ascii=False)

        # self.driver.quit()
        # self.driver.close()

        

if __name__ == '__main__':
    data_path = 'cbirc.gov.cn.list.行政处罚.监管局本级.json'
    cbirc = CbircCrawler()
    data = cbirc.main(data_path)
