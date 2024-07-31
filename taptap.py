from bs4 import Tag
from utils.driver import BaseDriver
from utils.simple_config import read_yaml_config


class TaptapSpider(BaseDriver):

    def __init__(self, url: str) -> None:
        self.url = url
    
    def parse_main_page(self, game_id: str, waitby_xpath: str):
        full_url = self.url.format(game_id)
        page_soup = self.get_page(full_url, waitby_xpath=waitby_xpath)
        with open('taptap.html', 'w', encoding='utf-8') as f:
            f.write(page_soup.prettify())

    def main(self, template_path: str):
        config = read_yaml_config(template_path)
        self.parse_main_page(
            game_id=config.game_id,
            waitby_xpath=config.xpath.all_reviews,
        )
       

if __name__ == '__main__':

    url = 'https://www.taptap.cn/app/{}/review'
    template_path = 'template/taptap.yaml'

    taptap = TaptapSpider(url)
    data = taptap.main(template_path=template_path)
