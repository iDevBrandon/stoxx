from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import time
import urllib.request

driver = webdriver.Chrome()
driver.get("https://stockcharts.com/")

# ticker symbols array
symbols = ['spy', 'aapl', 'msft', 'vxx', 'goog']
count = 1
for i in symbols:




    driver.find_element_by_id("nav-chartSearch-input").send_keys(i+Keys.RETURN)

    # elem.send_keys("spy")


    
    driver.implicitly_wait(2)
    imgUrl = driver.find_element_by_css_selector(".chartimg").get_attribute("src")


    opener = urllib.request.build_opener()
    opener.addheaders = [
        ('User-Agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1941.0 Safari/537.36')]
    urllib.request.install_opener(opener)
    urllib.request.urlretrieve(imgUrl, str(count) + ".jpg")
    count = count + 1
    driver.back()