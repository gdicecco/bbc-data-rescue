"""Extract text data from Breeding Bird Census pdfs"""

import os
import re
import string
from glob import glob

import pandas as pd

def convert_pdf_to_images(filename):
    """Convert a pdf to images"""
    filename = os.path.splitext(filename)[0]
    os.system("convert -density 350 -crop 0x0+0+315 {0}.pdf {0}.png".format(filename))

def ocr(filename):
    """OCR a file using tesseract"""
    filename = os.path.splitext(filename)[0]
    os.system("tesseract {0}.png {0}".format(filename))

def convert_pdfs_to_text(path):
    """Convert all PDFs in a directory to text

    Use convert to convert to images and tesseract for OCR
    
    """
    pdfs = glob(os.path.join(path, "*.pdf"))
    for pdf in pdfs:
        convert_pdf_to_images(pdf)
        
        #multi-page pdfs create multiple png files so loop over them
        pngs = glob(os.path.join(path, "*.png"))
        for png in pngs:
            ocr(png)

def cleanup_nonpara_pages(path, para_starts):
    """Remove text and png files for pages that aren't the core paragraph data"""
    for year in para_starts:
        pages  = range(para_starts[year] - 1) #pages are not zero indexed
        for page in pages:
            os.remove(os.path.join(path, "BBC{}-{}.txt".format(year, page)))
            os.remove(os.path.join(path, "BBC{}-{}.png".format(year, page)))

def combine_txt_files_by_yr(path, years):
    """Combine multiple text files into a single file for each year

    File names have the general format: BBC1988-0.txt
    
    """
    for year in years:
        with open(os.path.join(path, "bbc_combined_{}.txt".format(year)), 'w') as outfile:
            filenames = glob(os.path.join(path, "BBC{}*.txt".format(year)))
            sorted_filenames = sorted_nicely(filenames)
            for fname in sorted_filenames:
                with open(fname) as infile:
                    outfile.write(infile.read())

def sorted_nicely(l): 
    """ Sort the given iterable in the way that humans expect.

    From:
    http://stackoverflow.com/questions/2669059/how-to-sort-alpha-numeric-set-in-python
    
    """ 
    convert = lambda text: int(text) if text.isdigit() else text 
    alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key) ] 
    return sorted(l, key = alphanum_key)

def get_site(inputstring):
    """Check if line is location data and if so return location"""
    site_re = "^([0-9]{1,2})\. ([A-Z —-]{2,})"
    site_search = re.search(site_re, inputstring)
    if site_search:
        return (site_search.group(1), site_search.group(2))

def is_start_main_block(inputstring):
    """Check if line is the first line of the main block of data"""
    return inputstring.startswith("Location: ") or inputstring.startswith('Site Number: ')

def parse_block(block, site_name, site_num):
    """Parse a main data block from a BBC file"""
    # Cleanup difficult issues manually
    # Combination of difficult \n's and OCR mistakes
    replacements = {'Cemus': 'Census',
                    'Cov-\nerage': 'Coverage',
                    'Cov—\nerage': 'Coverage',
                    'Con-\ntinuity': 'Continuity',
                    'Conti-\nnuity': 'Continuity',
                    'Description\nof Plot': 'Description of Plot',
                    'De-\nscription of Plot': 'Description of Plot',
                    'Description of\nPlot': 'Description of Plot',
                    'Descrip-\ntion of Plot': 'Description of Plot',
                    'Solitary Vireo, 1,0;': 'Solitary Vireo, 1.0;',
                    'Common Yellowthroat, 14,0': 'Common Yellowthroat, 14.0',
                    'Bobolink; 9.0 territories': 'Bobolink, 9.0 territories',
                    "37°38'N,\n121°46lW": "37°38'N,\n121°46'W",
                    'Downy Wood-\npecker, 1,5': 'Downy Wood-\npecker, 1.5',
                    'Common\nYellowthroat, 4.5, Northern Flicker, 3.0': 'Common\nYellowthroat, 4.5; Northern Flicker, 3.0',
                    '\nWinter 1992\n': ' ', #One header line in one file got OCR'd for some reason
                    '20.9 h; 8 Visits (8 sunrise), 8, 15, 22, 29 April; 6, 13, 20, 27\nMay.': '20.9 h; 8 Visits (8 sunrise); 8, 15, 22, 29 April; 6, 13, 20, 27\nMay.',
                    'Anna’s Hummingbird, 2,0': 'Anna’s Hummingbird, 2.0',
                    '19.3 h; 11 visits (11 sunrise;': '19.3 h; 11 visits (11 sunrise);'
    }
    for replace in replacements:
        block = block.replace(replace, replacements[replace])
    p = re.compile(r'((?:Site Number|Location|Continuity|Size|Description of Plot|Edge|Topography and Elevation|Weather|Coverage|Census|Total|Visitors|Remarks|Other Observers|Acknowledgments)):') # 'Cemus' included as a mis-OCR of Census
    split_block = p.split(block)[1:] #discard first value; an empty string
    block_dict = {split_block[i]: split_block[i+1] for i in range(0, len(split_block), 2)}
    block_dict['SiteName'] = site_name
    block_dict['SiteNumInCensus'] = site_num
    return block_dict

def parse_txt_file(infile):
    """Parse a BBC text file"""
    first_site = True
    recording = False
    data = dict()
    for line in infile:
        site_info = get_site(line)
        if site_info:
            print(site_info)
            if not first_site:
                data[site_num] = parse_block(main_block, site_name, site_num)
            first_site = False
            site_num, site_name = site_info
            site_num = int(site_num)
            recording = False
        elif is_start_main_block(line):
            main_block = ''
            recording = True
        if recording:
            if line.strip():
                main_block += line
    return(data)

def get_latlong(location):
    """Extract the latitude and longitude from the Location data"""
    regex = "([0-9]{1,3})°([0-9]{1,2})[ ]*[’|'|‘]N,[ |\\n]([0-9]{2,3})°([0-9]{1,2})[’|'|‘]W"
    search = re.search(regex, location)
    if search:
        lat_deg, lat_min = int(search.group(1)), int(search.group(2))
        long_deg, long_min = int(search.group(3)), int(search.group(4))
        lat_decdeg = lat_deg + lat_min / 60.0
        long_decdeg = long_deg + long_min / 60.0
        return (lat_decdeg, long_decdeg)

def extract_counts(data, site, year):
    """Split the Census text block into species and counts"""
    census_data = data['Census']
    census_data = re.sub(r'\([^)]+\)', '', census_data) # remove parentheticals (which include ;)
    census_data = census_data.replace('territories', '')
    census_data = census_data.split(';')
    counts_data = pd.DataFrame(columns = ['site', 'year', 'species', 'count', 'status'])
    for record in census_data:
        if record.strip(): # Avoid occasional blank lines
            species, count = record.split(',')
            species = get_cleaned_species(species)
            counts_record = pd.DataFrame({'year': year,
                                          'siteID': site,
                                          'species': [species],
                                          'count': [count.strip(' .\n')],
                                          'status': ['resident']})
            counts_data = counts_data.append(counts_record, ignore_index = True)

    if 'Visitors' in data:
        visitor_data = data['Visitors'].split(',')
        for species in visitor_data:
            species = get_cleaned_species(species)
            counts_record = pd.DataFrame({'year': year,
                                          'siteID': site,
                                          'species': [species],
                                          'count': [None],
                                          'status': ['visitor']})
            counts_data = counts_data.append(counts_record, ignore_index = True)
    
    return counts_data

def get_clean_size(size_data):
    """Remove units, notes, and whitespace"""
    size = size_data.split('ha')[0]
    return float(size.strip(' .\n'))

def get_cleaned_species(species):
    """Cleanup species names"""
    species = species.strip().replace('-\n', '-')
    species = species.replace('\n', ' ')
    species = species.strip()
    return species


def get_cleaned_string(string_data):
    """Do basic cleanup on string data

    1. Remove \n's
    2. Strip whitespace

    """

    string_data = string_data.strip().replace('-\n', '')
    string_data = string_data.replace('\n', ' ')
    string_data = string_data.strip()
    return string_data

def clean_string_fields(site_data):
    """Do basic cleanup on simple string fields for a site"""
    string_fields = ['Description of Plot', 'Edge', 'Location', 'Remarks', 'SiteName']
    for field in string_fields:
        if field in site_data:
            site_data[field] = get_cleaned_string(site_data[field])
    return site_data

def extract_coverage(coverage):
    """Extract number of hours and number of visits from Coverage"""
    coverage = get_cleaned_string(coverage)
    extracted = dict()
    re_with_times = '([0-9]{1,3}\.{0,1}[0-9]{0,2}) h; ([0-9]{1,2}) [V|v]isits \(([^)]+)\);(.*)'
    re_no_times = '([0-9]{1,3}\.{0,1}[0-9]{0,2}) h; ([0-9]{1,2}) [V|v]isits;(.*)'
    search = re.search(re_with_times, coverage)
    if search:
        extracted['hours'] = float(search.group(1))
        extracted['visits'] = int(search.group(2))
        extracted['times'] = search.group(3)
        extracted['notes'] = search.group(4)
    else:
        search = re.search(re_no_times, coverage)
        extracted['hours'] = float(search.group(1))
        extracted['visits'] = int(search.group(2))
        extracted['notes'] = search.group(3)
    return extracted

def extract_total(total):
    """Extract the total number of species and total territories"""
    total = get_cleaned_string(total)
    extracted = dict()
    regex = '([0-9]{1,3}) species; ([0-9]{1,4}\.{0,1}[0-9]{0,1}) territories \(([^)]+)\).'
    search = re.search(regex, total)
    extracted['total_species'] = int(search.group(1))
    extracted['total_territories'] = float(search.group(2))
    extracted['total_terr_notes'] = search.group(3)
    return extracted

def extract_continuity(continuity, year):
    """Extract establishment year and number of years surveyed"""
    continuity = get_cleaned_string(continuity)
    extracted = dict()
    if 'New' in continuity:
        extracted['established'] = year
        extracted['length'] = 1
    else:
        if ';' in continuity:
            established, length = continuity.split(';')
        else:
            # some ; delimiters are mis-OCR'd as ,
            established, length = continuity.split(',')
        established = established.replace('Established', '').strip()
        length = length.replace('yr.', '').replace('consecutive', '').replace('intermittent', '').strip()
        extracted['established'] = established
        extracted['length'] = length
    return extracted

def extract_site_data(site_data):
    """Extract data for a site"""
    site_data['Latitude'], site_data['Longitude'] = get_latlong(site_data['Location'])
    site_data['Size'] = get_clean_size(site_data['Size'])
    site_data['Coverage'] = extract_coverage(site_data['Coverage'])
    site_data['Total'] = extract_total(site_data['Total'])
    site_data['Continuity'] = extract_continuity(site_data['Continuity'], year)
    site_data = clean_string_fields(site_data)
    return site_data

def get_sites_table(site_data):
    """Put site level data into a dataframe"""
    sites_table = pd.DataFrame({'siteID': [site_data['SiteNumInCensus']],
                                'sitename': [site_data['SiteName']],
                                'latitude': [site_data['Latitude']],
                                'longitude': [site_data['Longitude']],
                                'location': [site_data['Location']],
                                'description': [site_data['Description of Plot']]})
    return sites_table

def get_census_table(site_data, year):
    """Put census level data into a dataframe"""
    census_table = pd.DataFrame({'siteID': [site_data['SiteNumInCensus']],
                                 'sitename': [site_data['SiteName']],
                                 'siteNumInCensus': [site_data['SiteNumInCensus']],
                                 'year': [year],
                                 'established': [site_data['Continuity']['established']],
                                 'ts_length': [site_data['Continuity']['length']],
                                 'cov_hours': [site_data['Coverage']['hours']],
                                 'cov_visits': [site_data['Coverage']['visits']],
                                 'cov_times': [site_data['Coverage'].get('times', None)],
                                 'cov_notes': [site_data['Coverage']['notes']],
                                 'richness': [site_data['Total']['total_species']],
                                 'territories': [site_data['Total']['total_territories']],
                                 'terr_notes': [site_data['Total']['total_terr_notes']],
                                 'weather': [site_data['Weather']]
                             })
    return census_table


para_starts = {1988: 4, 1989: 6, 1990: 6, 1991: 7,
               1992: 7, 1993: 7, 1994: 7, 1995: 6}
data_path = "./data/raw_datasets/BBC_pdfs/"
#convert_pdfs_to_text(data_path)
#cleanup_nonpara_pages(data_path, para_starts)
#combine_txt_files_by_yr(data_path, para_starts.keys())

counts_table = pd.DataFrame(columns = ['siteID', 'year', 'species',
                                       'count', 'status'])
site_table = pd.DataFrame(columns = ['siteID', 'latitude', 'longitude',
                                     'location', 'description'])
census_table = pd.DataFrame(columns = ['siteID', 'sitename', 'siteNumInCensus',
                                       'year', 'established', 'ts_length', 'cov_hours',
                                       'cov_visits', 'cov_times', 'cov_notes',
                                       'richness', 'territories', 'terr_notes',
                                       'weather'])
years = [1991,]

for year in years:
    datafile = os.path.join(data_path, "bbc_combined_{}.txt".format(year))
    with open(datafile) as infile:
        data = parse_txt_file(infile)
        for site in data:
            print(site)
            data[site] = extract_site_data(data[site])
            counts_table = counts_table.append(extract_counts(data[site], site, year),
                                               ignore_index=True)
            site_table = site_table.append(get_sites_table(data[site]),
                                           ignore_index=True)
            census_table = census_table.append(get_census_table(data[site], year),
                                               ignore_index=True)

counts_table = counts_table[['siteID', 'year', 'species', 'count', 'status']]
site_table = site_table[['siteID', 'latitude', 'longitude',
                         'location', 'description']]
census_table = census_table[['siteID', 'sitename', 'siteNumInCensus',
                                       'year', 'established', 'ts_length', 'cov_hours',
                                       'cov_visits', 'cov_times', 'cov_notes',
                                       'richness', 'territories', 'terr_notes',
                                       'weather']]

#TODO:

# 1. Site numbers need to be converted to siteIDs based on lat/long/name.
#    Multiple sites share the same lat/long, so it is insufficient on it's own
