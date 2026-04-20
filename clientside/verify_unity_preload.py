import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

service = Service(r'C:\Users\licha\.wdm\drivers\chromedriver\win64\147.0.7727.57\chromedriver-win32\chromedriver.exe')
options = webdriver.ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--window-size=1920,1080')

driver = webdriver.Chrome(service=service, options=options)
try:
    driver.get('http://localhost:3000/dashboard')
    wait = WebDriverWait(driver, 60)
    wait.until(EC.presence_of_element_located((By.ID, 'gameStageCover')))
    wait.until(EC.presence_of_element_located((By.ID, 'unityGameplayFramePreload')))
    wait.until(EC.presence_of_element_located((By.ID, 'unityGameplayFrame')))
    print('found elements')
    countdown = driver.find_element(By.ID, 'roundCountdown').text
    print('initial countdown', countdown)

    # Wait for preload frame and active frame source assignment.
    start = time.time()
    while time.time() - start < 120:
        cover_hidden = driver.execute_script('return document.getElementById("gameStageCover").hidden;')
        preload_src = driver.execute_script('return document.getElementById("unityGameplayFramePreload").dataset.frameSrc;')
        main_src = driver.execute_script('return document.getElementById("unityGameplayFrame").dataset.frameSrc;')
        print('preload_src', preload_src, 'main_src', main_src, 'cover_hidden', cover_hidden)
        if preload_src and main_src:
            break
        time.sleep(1)

    # Wait until countdown reaches 00:00.
    start = time.time()
    while time.time() - start < 240:
        text = driver.find_element(By.ID, 'roundCountdown').text
        print('countdown', text)
        if text == '00:00':
            break
        time.sleep(1)

    cover_hidden = driver.execute_script('return document.getElementById("gameStageCover").hidden;')
    main_src = driver.execute_script('return document.getElementById("unityGameplayFrame").dataset.frameSrc;')
    preload_src = driver.execute_script('return document.getElementById("unityGameplayFramePreload").dataset.frameSrc;')
    active_class = driver.execute_script('return document.getElementById("unityGameplayFrame").className;')
    preload_class = driver.execute_script('return document.getElementById("unityGameplayFramePreload").className;')
    print('final state:', {
        'cover_hidden': cover_hidden,
        'main_src': main_src,
        'preload_src': preload_src,
        'active_class': active_class,
        'preload_class': preload_class,
    })
finally:
    driver.quit()
