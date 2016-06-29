"""Extract text data from Breeding Bird Census pdfs"""

import os
import re
import string
from glob import glob
from functools import lru_cache

import pandas as pd
from fuzzywuzzy import fuzz, process

def get_site(inputstring):
    """Check if line is location data and if so return location"""
    site_re = "^([0-9]{1,2})\. ([A-Z —-]{2,})"
    site_search = re.search(site_re, inputstring)
    if site_search:
        return (site_search.group(1), site_search.group(2))

def is_start_main_block(inputstring):
    """Check if line is the first line of the main block of data"""
    return inputstring.startswith("Location: ") or inputstring.startswith('Site Number: ')

def parse_block(block, site_name, site_num, year):
    """Parse a main data block from a BBC file"""
    # Cleanup difficult issues manually
    # Combination of difficult \n's and OCR mistakes
    replacements = {'Cemus': 'Census',
                    'Description Oi Plot': 'Description of Plot',
                    'Acknowledgmentsz': 'Acknowledgments: ',
                    'Other Observers:]': 'Other Observers: ',
                    'Other 0berservers': 'Other Observers: ',
                    '0ther Observerers': 'Other Observers: ',
                    'Other 0bservers': 'Other Observers: ',
                    'Other Observers.': 'Other Observers:',
                    'Other Observers]': 'Other Observers:',
                    'Continnity': 'Continuity',
                    'lViagnolia': 'Magnolia',
                    'lVildlife': 'Wildlife',
                    'Mallard ): American Black Duck hybrid': 'Mallard x American Black Duck hybrid',
                    'Observerszj': 'Observers',
                    'Bobolink; 9.0 territories': 'Bobolink, 9.0 territories',
                    "37°38'N, 121°46lW": "37°38'N, 121°46'W",
                    'Common Yellowthroat, 4.5, Northern Flicker, 3.0': 'Common Yellowthroat, 4.5; Northern Flicker, 3.0',
                    'Red-bellied Woodpecker, 2.0, Carolina Chickadee, 2.0': 'Red-bellied Woodpecker, 2.0; Carolina Chickadee, 2.0',
                    'Winter 1992': ' ', #One header line in one file got OCR'd for some reason
                    'nuLquu “1:10': ' ',
                    'nululuu 1:1:1.)': ' ',
                    '20.9 h; 8 Visits (8 sunrise), 8, 15, 22, 29 April; 6, 13, 20, 27 May.': '20.9 h; 8 Visits (8 sunrise); 8, 15, 22, 29 April; 6, 13, 20, 27 May.',
                    '19.3 h; 11 visits (11 sunrise;': '19.3 h; 11 visits (11 sunrise);',
                    'Foster Plantation; 42"7’N': 'Foster Plantation; 42°7’N',
                    'Hermit Thrush, 4.5 (18), Black-throatcd Green Warbler': 'Hermit Thrush, 4.5 (18); Black-throated Green Warbler', # Fixes both delimiter and selling of throated
                    '39"] 2‘N, 76°54’W': '39°12‘N, 76°54’W',
                    "42°“7'N, 77°45’W": "42°7'N, 77°45’W",
                    '41°4\'N, 76"7’W': "41°4'N, 76°7’W",
                    'w‘sits': 'visits',
                    '79513’W': '79°13’W',
                    'Continuity.': 'Continuity:',
                    'Continuity"': 'Continuity:',
                    "40°44'N, 7 D50’W": "40°44'N, 75°50’W",
                    "41350'N, 71°33'W": "41°50'N, 71°33'W",
                    '44°57’N, 68D41’W': '44°57’N, 68°41’W',
                    '18.8 11; 11 Visits': '18.8 h; 11 Visits',
                    "Descripn'on of Plot": "Description of Plot",
                    '41 c’42’N, 73°13’VV': "41°42'N, 73°13'W",
                    'Northern Rough-winged Swallow. 0.5': 'Northern Rough-winged Swallow, 0.5',
                    'Warbling Vireo, 1.0, Northern Cardinal, 1.0': 'Warbling Vireo, 1.0; Northern Cardinal, 1.0',
                    'Wood Thrush, 3.0 (18), American Redstart, 3.0': 'Wood Thrush, 3.0; American Redstart, 3.0',
                    'study-hrs': 'study-hours',
                    'studyhours': 'study-hours',
                    'Nuttall’s Woodpecker, 3 (9; 2N),':'Nuttall’s Woodpecker, 3 (9; 2N);',
                    '38°35’45”N\', 76°45’46"W': '38°35’45”N, 76°45’46"W',
                    'Northern Parula 8': 'Northern Parula, 8',
                    '47°08’N, 99°] 5’ W': '47°08’N, 99°15’ W',
                    'Yellow Warbler, 1,’ Clay-colored Sparrow, 1,Savannah Sparrow, 1;': 'Yellow Warbler, 1; Clay-colored Sparrow, 1; Savannah Sparrow, 1;',
                    'Established 1993; 2 )n‘.': 'Established 1993; 2.',
                    'Established l983': 'Established 1983',
                    'Established 1978; 18 you': 'Established 1978; 18 yr.',
                    'This plot is part of a larger plot that was ﬁrst censused in 1981.': '',
                    'Ruby-throatcd Hummingbird': 'Ruby-throated Hummingbird',
                    'RuHed Grouse': 'Ruffed Grouse',
                    '\Varbler': "Warbler",
                    'VVarbler': "Warbler",
                    'Common Yellowthroat 3': 'Common Yellowthroat, 3',
                    'all known to breed in immediate vicinity': '',
                    'and a number of vagrants': '',
                    "Utner Ubservers": "Other Observers",
                    'Dovmy': 'Downy',
                    "W'oodpecker": "Woodpecker",
                    "\700d Thrush": "Wood Thrush",
                    "\form-eating Warbler": "Worm-eating Warbler",
                    "Cliﬂ' Swallow": "Cliff Swallow",
                    'Cliﬂ\ Swallow"': 'Cliff Swallow',
                    'Downy Woodpecknululuu I JHJ er': 'Downy Woodpecker',
                    'unidentiﬁed Accipiter': 'Accipiter sp.',
                    "Traill’s Flycatcher": "Willow Flycatcher",
                    'Eastern Titmouse': 'Tufted Titmouse',
                    'Common Barn Owl': 'Barn Owl',
                    'Common Bushtit': 'Bushtit',
                    'Yellow-shafted Flicker': 'Northern Flicker',
                    'Yellowshafted Flicker': 'Northern Flicker',
                    'Common Barn-Owl': 'Barn Owl',
                    'Northern Parula Warbler': 'Northern Parula',
                    'Yellow-rumped,': 'Yellow-rumped Warbler,',
                    'Common Crow': 'American Crow',
                    ', Raven,': ', Common Raven,',
                    '; Raven,': '; Common Raven,',
                    '+_': '+'
    }
    block = get_cleaned_string(block)
    for replacement in replacements:
        if replacement in block:
            print("Replacing {} with {}".format(replacement, replacements[replacement]))
            block = block.replace(replacement, replacements[replacement])
    block = get_clean_block(block)
    p = re.compile(r'((?:Site Number|Location|Continuity|Previously called|Size|Description of Plot|Edge|Topography and Elevation|Weather|Coverage|Census|Fledglings|Nests and Fledglings|Fledglings Seen|Fledglings Noted|Total|Visitors|Nests Found|Remarks|Observers|Other Observers|Other Observer|Acknowledgments)):')
    split_block = p.split(block)[1:] #discard first value; an empty string
    block_dict = {split_block[i]: split_block[i+1] for i in range(0, len(split_block), 2)}
    block_dict['SiteName'] = site_name
    block_dict['SiteNumInCensus'] = site_num * 10000 + year
    return block_dict

def parse_txt_file(infile, year):
    """Parse a BBC text file"""
    first_site = True
    recording = False
    data = dict()
    for line in infile:
        site_info = get_site(line)
        if site_info:
            if not first_site:
                data[site_num] = parse_block(main_block, site_name, site_num, year)
            first_site = False
            site_num, site_name = site_info
            site_name = site_name.replace('—', '-')
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
    regex =  """([0-9]{1,2})[ ]*[°05C]([0-9]{1,2}) *[’|'|‘][0-9]{0,2}["|”]{0,1} *N,[ |\\n]([0-9]{2,3})[ ]*[°05C]([0-9]{1,2})[ ]*[’|'|‘][0-9]{0,2}["|”]{0,1} *[W|V|;|.]"""
    search = re.search(regex, location)
    if search:
        lat_deg, lat_min = int(search.group(1)), int(search.group(2))
        long_deg, long_min = int(search.group(3)), int(search.group(4))
        lat_decdeg = lat_deg + lat_min / 60.0
        long_decdeg = long_deg + long_min / 60.0
        return (lat_decdeg, long_decdeg)

def extract_counts(data, year):
    """Split the Census text block into species and counts"""
    census_data = data['Census']
    census_data = re.sub(r'\([^)]+\)', '', census_data) # remove parentheticals (which include ;)
    census_data = census_data.replace('territories', '')
    census_data = census_data.split(';')
    comma_decimal_re = ', ([0-9]{1,2}),([0-9])'
    period_delimiter_re = ''
    counts_results = []
    for record in census_data:
        record = record.strip()
        if record: # Avoid occasional blank lines
            if record.count(',') == 2: # Typically a mis-OCR'd decimal in the count
                search = re.search(comma_decimal_re, record)
                if search:
                    species = record.split(',')[0]
                    count = '{}.{}'.format(search.group(1), search.group(2))
            elif record.count(',') == 0 and record.count('.') == 2: # Comma mis-OCR'd as period
                species, count = record.split('.', maxsplit=1)
            else:
                species, count = record.split(',')
            species = get_cleaned_species(species)
            if species:
                counts_record = [year, data['SiteNumInCensus'], species,
                                 count.strip(' .\n'), 'breeder']
                counts_results.append(counts_record)

    if 'Visitors' in data:
        visitor_data = data['Visitors'].split(',')
        for species in visitor_data:
            if ' and ' in species:
                new_species = species.split(' and ')
                census_data.append(new_species[0])
                census_data.append(new_species[1])
                continue
            species = get_cleaned_species(species)
            if species:
                counts_record = [year, data['SiteNumInCensus'], species,
                                 None, 'visitor']
                counts_results.append(counts_record)

    counts_data = pd.DataFrame(counts_results, columns=['year',
                                                        'siteNumInCensus',
                                                        'species',
                                                        'count',
                                                        'status'])
    return counts_data

def get_clean_block(block):
    """Clean up unicode characters and common OCR errors in blocks"""
    replacements = {'ﬁ': 'fi',
                    'ﬂ': 'fi',
                    '—': '-',
                    "’": "'",
                    "‘": "'",
                    '”': '"',
                    '“': '"',
                    'km3': 'km2',
                    'kmz': 'km2',
                    '\\N': 'W',
                    'VV': 'W',
                    'lVI': 'M',}
    for replacement in replacements:
        if replacement in block:
            block = block.replace(replacement, replacements[replacement])
    return(block)

def get_clean_size(size_data):
    """Remove units, notes, and whitespace"""
    size = size_data.split('ha')[0]
    size = size.replace('.]', '1')
    size = size.replace('.?)', '3')
    return float(size.strip(' .\n'))

@lru_cache(maxsize=None)
def get_cleaned_species(species):
    """Cleanup species names"""
    if not species: return None
    species = species.replace('-\n', '-')
    species = species.replace('\n', ' ')
    species = species.replace('species', 'sp.')
    species = species.strip(' .')
    species = re.sub(r'\([^)]+\)', '', species) #remove parenthetical
    matched_species = process.extractOne(species, valid_sp_names,
                                         processor=str, # Needed to hack around https://github.com/seatgeek/fuzzywuzzy/issues/77
                                         scorer=fuzz.ratio)
    if matched_species[1] >= 70:
        if matched_species[1] <100: matched[species] = matched_species
        species = matched_species[0]
    else:
        unmatched.append((species, matched_species))
        species = None
    return species


def get_cleaned_string(string_data):
    """Do basic cleanup on string data

    1. Remove \n's
    2. Strip whitespace

    """

    string_data = string_data.strip().replace('-\n', '')
    string_data = string_data.strip().replace('—\n', '')
    string_data = string_data.replace('\n', ' ')
    string_data = string_data.replace('.?)', '.3')
    string_data = string_data.strip(' \n,')
    return string_data

def clean_string_fields(site_data):
    """Do basic cleanup on simple string fields for a site"""
    string_fields = ['Description of Plot', 'Edge', 'Location', 'Remarks',
                     'SiteName', 'Weather']
    for field in string_fields:
        if field in site_data:
            site_data[field] = get_cleaned_string(site_data[field])
    return site_data

def extract_coverage(coverage):
    """Extract number of hours and number of visits from Coverage"""
    coverage = get_cleaned_string(coverage)
    extracted = dict()
    re_modern = '([0-9]{1,3}\.{0,1}[0-9]{0,2}) h; ([0-9]{1,2}) [V|v]isits(.*)'
    re_modern_no_visits = '([0-9]{1,3}\.{0,1}[0-9]{0,2}) h'
    re_1988 = '([0-9]{1,3}) [V|v]isits; ([0-9]{1,3}) study[-|—]hours;(.*)'
    re_1988_no_visits = '([0-9]{1,3}) study[-|—]hours[;. ](.*)'
    if year > 1988:
        search = re.search(re_modern, coverage)
        search_no_visits = re.search(re_modern_no_visits, coverage)
    else:
        search = re.search(re_1988, coverage)
        search_no_visits = re.search(re_1988_no_visits, coverage)
    if search:
        extracted['hours'] = float(search.group(1))
        extracted['visits'] = int(search.group(2))
        extracted['notes'] = search.group(3)
    else:
        extracted['hours'] = float(search_no_visits.group(1))
        extracted['visits'] = None
        extracted['notes'] = None
    return extracted

def extract_total(total):
    """Extract the total number of species and total territories"""
    total = get_cleaned_string(total)
    extracted = dict()
    regex = '([0-9]{1,3}) species; ([0-9]{1,4}\.{0,1}[0-9]{0,1}) (territories|territorial males) \(([^)]+)\).'
    search = re.search(regex, total)
    extracted['total_species'] = int(search.group(1))
    extracted['total_territories'] = float(search.group(2))
    extracted['total_terr_notes'] = search.group(4)
    return extracted

def extract_continuity(continuity, year):
    """Extract establishment year and number of years surveyed"""
    continuity = get_cleaned_string(continuity)
    removals = ['Established', 'years', 'yrs', 'yr', 'consecutive', 'intermittent']
    for removal in removals:
        continuity = continuity.replace(removal, '').strip(' \n.')
    continuity = re.sub('\(([^)]+)\)', '', continuity)
    extracted = dict()
    if 'New' in continuity:
        extracted['established'] = year
        extracted['length'] = 1
    else:
        if ';' in continuity:
            established, length = continuity.split(';')
        elif ',' in continuity:
            # some ; delimiters are mis-OCR'd as ,
            established, length = continuity.split(',')
        elif ' ' in continuity:
            # pre-1989 these are just space delimited
            established, length = continuity.split(' ')
        else:
            # If there is only a year value
            established = continuity
            length = None
        extracted['established'] = int(established)
        extracted['length'] = int(length) if length else None
    return extracted

def extract_site_data(site_data):
    """Extract data for a site"""
    site_data['Latitude'], site_data['Longitude'] = get_latlong(site_data['Location'])
    site_data['Size'] = get_clean_size(site_data['Size'])
    if 'Coverage' in site_data:
        site_data['Coverage'] = extract_coverage(site_data['Coverage'])
    else:
        site_data['Coverage'] = dict()
    site_data['Total'] = extract_total(site_data['Total'])
    site_data['Continuity'] = extract_continuity(site_data['Continuity'], year)
    site_data = clean_string_fields(site_data)
    return site_data

def get_sites_table(site_data):
    """Put site level data into a dataframe"""
    sites_table = pd.DataFrame({'siteNumInCensus': [site_data['SiteNumInCensus']],
                                'sitename': [site_data['SiteName']],
                                'latitude': [site_data['Latitude']],
                                'longitude': [site_data['Longitude']],
                                'location': [site_data['Location']],
                                'description': [site_data['Description of Plot']]})
    return sites_table

def get_census_table(site_data, year):
    """Put census level data into a dataframe"""
    #sometimes Weather doesn't exist before 1989
    weather = site_data['Weather'] if 'Weather' in site_data else None
    previously_called = site_data['Previously called'] if 'Previously called' in site_data else None
    census_table = pd.DataFrame({'sitename': [site_data['SiteName']],
                                 'siteNumInCensus': [site_data['SiteNumInCensus']],
                                 'year': [year],
                                 'established': [site_data['Continuity']['established']],
                                 'ts_length': [site_data['Continuity']['length']],
                                 'cov_hours': [site_data['Coverage'].get('hours', None)],
                                 'cov_visits': [site_data['Coverage'].get('visits', None)],
                                 'cov_times': [site_data['Coverage'].get('times', None)],
                                 'cov_notes': [site_data['Coverage'].get('notes', None)],
                                 'area': [site_data['Size']],
                                 'richness': [site_data['Total']['total_species']],
                                 'territories': [site_data['Total']['total_territories']],
                                 'terr_notes': [site_data['Total']['total_terr_notes']],
                                 'weather': [weather],
                                 'previously_called': [previously_called]
                             })
    return census_table

def get_valid_sp_names(sp_names_file):
    """Get valid species names from name corrections file"""
    names_data = pd.read_csv(sp_names_file)
    names_data = names_data[names_data['Notes'] != 'delete']
    names_data.loc[names_data['cleaned_name'].isnull(),'cleaned_name'] = names_data['original_name']
    valid_names = list(names_data['cleaned_name'].drop_duplicates())
    return(valid_names)

data_path = "./data/"
valid_sp_names = get_valid_sp_names("data/bbc_species_corrections.csv")
unmatched = []
matched = {}

counts_table = pd.DataFrame(columns = ['siteNumInCensus', 'year', 'species',
                                       'count', 'status'])
site_table = pd.DataFrame(columns = ['siteNumInCensus', 'sitename', 'latitude',
                                     'longitude', 'location', 'description'])
census_table = pd.DataFrame(columns = ['sitename', 'siteNumInCensus',
                                       'year', 'established', 'ts_length', 'cov_hours',
                                       'cov_visits', 'cov_times', 'cov_notes', 'area',
                                       'richness', 'territories', 'terr_notes',
                                       'weather'])
years = range(1988,1996)

for year in years:
    print("\nProcessing {} data...\n".format(year))
    datafile = os.path.join(data_path, "bbc_combined_{}.txt".format(year))
    with open(datafile) as infile:
        data = parse_txt_file(infile, year)
        for site in data:
            data[site] = extract_site_data(data[site])
            counts_table = counts_table.append(extract_counts(data[site], year),
                                               ignore_index=True)
            site_table = site_table.append(get_sites_table(data[site]),
                                           ignore_index=True)
            census_table = census_table.append(get_census_table(data[site], year),
                                               ignore_index=True)

# Provide information on fuzzy matching for error checking
print("\nUnmatched species:\n")
print(unmatched)
print()
print("\nFuzzy matched species:\n")
print("RawSpecies, MatchedSpecies, Ratio")
for raw_species in matched:
    print('{}, {}, {}'.format(raw_species, matched[raw_species][0], matched[raw_species][1]))

site_table_simp = site_table[['sitename', 'latitude', 'longitude']]
unique_sites = site_table_simp.drop_duplicates().reset_index(drop=True)
unique_sites['siteID'] = unique_sites.index + 1
site_table = pd.merge(unique_sites, site_table, on = ['sitename', 'latitude', 'longitude'])
siteID_links = site_table[['siteNumInCensus', 'siteID']]
counts_table = pd.merge(counts_table, siteID_links, on = ["siteNumInCensus"])
census_table = pd.merge(census_table, siteID_links, on = ["siteNumInCensus"])

counts_table = counts_table[['siteID', 'year', 'species', 'count', 'status']]
site_table = site_table[['siteID', 'sitename', 'latitude',
                         'longitude', 'location', 'description']]
census_table = census_table[['siteID', 'sitename', 'siteNumInCensus',
                                       'year', 'established', 'ts_length', 'cov_hours',
                                       'cov_visits', 'cov_times', 'cov_notes', 'area',
                                       'richness', 'territories', 'terr_notes',
                                       'weather']]
counts_table.to_csv('output/bbc_counts.csv', index=False)
census_table.to_csv('output/bbc_censuses.csv', index=False)
site_table.to_csv('output/bbc_sites.csv', index=False)
