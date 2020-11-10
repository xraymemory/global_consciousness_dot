import requests
import time
import colorsys
import secrets

from rgbxy import Converter
from bs4 import BeautifulSoup as bs
from numpy import interp
from PIL import Image


class GcpDot:

    def __init__(self, bridge_ip="192.168.1.238", connect=False):
        '''Creates GcpDot object and optionally connects to Phillips Hue'''

        # Internals
        self._rgb_conv = Converter()
        self._BASE_GRADIENT_COLOR = (239, 239, 255)
        self.stats = []
        self.connected = False

        if connect:
            self.API_BASE_IP = bridge_ip
            self.light = self._connect()
            self.connected = True

    def _connect(self):
        '''Attemps to connect using phue Bridge. Assumes only one light'''

        from phue import Bridge
        b = Bridge(self.API_BASE_IP)
        b.connect()
        gcp = b.lights[-1]
        return gcp

    def _run_headless_driver(self):
        ''' 
        Run headless Chrome to scrape GCP PHP data. Interpolates dot height 
        on the chart and normalizes it to a percentage between 0.0 and 1.0,
        maps it to appropriate color, generates timestamp, and then shifts
        by first three significant digits

        Appends entry to self.stats dict with the shape

        {"dot_height_raw": float, "gcp_index": float, 
        "ts": float, "color": string, "gcp_index_shifted": int}

        Returns gcp_index as float
        '''

        import os  
        from selenium import webdriver  
        from selenium.webdriver.support.ui import WebDriverWait
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
        #from xvfbwrapper import Xvfb

        high = 0
        delay = 3

        driver = webdriver.Chrome(ChromeDriverManager(log_level=0).install())

        driver.implicitly_wait(3)
        driver.get("https://gcpdot.com/gcpchart.php")

        try:
            ''' love 2 traverse the dom '''
            chart_height = driver.find_element_by_id('gcpChartShadow').get_attribute("height")
            dot = driver.find_elements_by_tag_name('div')[-1]
            dot_id = dot.get_attribute('id')
            dot_height = driver.find_element_by_id(dot_id).value_of_css_property('top');
            dot_height = dot_height.replace('px', '')


            ''' The Javascript animation logic introduces junk data not seen in the actual numbers
                in order to raise or lower the dot. In this case, we will just resample.'''

            if (dot_height > chart_height):
                driver.close()
                return self._run_headless_driver()

            ''' Map dot height into domain [0.0...1.0] rather than raw css property value'''
            high = interp(float(dot_height), [0, float(chart_height)], [0.0, 1.0])

            
            if (len(str(high)) > 3):
                shift = float("0."+str(high)[3:])
            else:
                shift = high
            
            stat_dict = {"dot_height_raw": float(dot_height), "gcp_index": high, "ts": time.time(), "color":self._color_switch(high), "gcp_index_shifted": shift }
            self.stats.append(stat_dict)

        except (TimeoutException, Exception) as e:
            print("Sick exception: " + str(e))
            raise e
            
        driver.close()
        return high

    def _generate_gradient(self, colour1, colour2, width, height):
        '''Generates and displays a vertical gradient.'''

        base = Image.new('RGB', (width, height), colour1)
        top = Image.new('RGB', (width, height), colour2)
        mask = Image.new('L', (width, height))
        mask_data = []

        ''' Gradient happens here, simple linear from top to bottom '''
        for y in range(height):
            for x in range(width):
                mask_data.append(int(255 * (y / height)))

        mask.putdata(mask_data)
        base.paste(top, (0, 0), mask)
        base.show()
        base.close()


    def _color_switch(self, high):
        ''' Map gcp_index ranges to colors, as specified on https://gcpdot.com/'''

        if (high == 0):
            color = "gray"
        elif (high < 0.05):
            color = "red"
        elif (high >= 0.05 and high < 0.10):
            color = "orange"
        elif (high >= 0.10 and high < 0.40):
            color = "yellow"
        elif (high >= 0.40 and high < 0.90):
            color = "green"
        elif (high >= 0.90 and high <= 0.95):
            color = "teal"
        elif (high >= 0.95 and high <= 1.0):
            color = "blue"
        else:
            color = "gray"

        return color

    def update_hue_color(self, l=0.4, s=0.4):
        ''' Gets latest reading from GCP and updates Phillips Hue bulb if connected'''

        high = self._run_headless_driver()
        color = self._color_switch(high)

        rgb = colorsys.hls_to_rgb(high, l, s)

        if self.connected:
            self.light.xy = self.rgb_conv.rgb_to_xy(rgb[0], rgb[1], rgb[2])

        return color

    def _get_entropy(self, labels, length=4):
        '''Uses scipy.entropy to determine Shannon Entropy'''

        import pandas as pd
        from scipy.stats import entropy

        pd_series = pd.Series(labels)
        counts = pd_series.value_counts()
        ent = entropy(counts)

        print("Entropy stats")
        print("Shannon Entropy: " + str(ent))

    def sample(self):
        ''' Samples one timestamped data point from GCP Dot '''

        high = self._run_headless_driver()
        return self.stats[-1]

    def random(self, new=True):
        ''' Provide similar one-shot behavior as random.random() '''

        if new:
            num = self.sample()
        else:
            if (len(self.stats) < 1):
                self.random(new=True)
            num = secrets.choice(self.stats)

        return num["gcp_index_shifted"]
        
    def gather(self, limit=420, mod=5, sleep=3, output=True):
        ''' Gathers `limit` sampled data points and displays them at every `mod` interval '''
        
        while (limit > 0): 
            
            self.sample()
            time.sleep(sleep)

            if ((len(self.stats) % mod == 0) and output):
                for item in self.stats:
                    print(str(item["gcp_index_shifted"]))

if __name__ == "__main__":
    
    g = GcpDot()
    g.random()
