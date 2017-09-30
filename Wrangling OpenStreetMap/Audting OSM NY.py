import csv
import codecs
import pprint
import re
import xml.etree.cElementTree as ET

import cerberus

import schema

OSM_PATH = "newyork-sample.osm"

NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"

LOWER_COLON = re.compile(r'^([a-z]|_)+:([a-z]|_)+')
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')
LOWER = re.compile(r'^([a-z]|_)*$')


SCHEMA = schema.schema

# Make sure the fields order in the csvs matches the column order in the sql table schema
NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']


def shape_element(element, node_attr_fields=NODE_FIELDS, way_attr_fields=WAY_FIELDS,
                  problem_chars=PROBLEMCHARS, default_tag_type='regular'):
    """Clean and shape node or way XML element to Python dict"""

    node_attribs = {}
    node_tags = {}
    way_attribs = {}
    way_tags = {}
    way_nodes = []
    way_nodes_record = {}
    tags = []  # Handle secondary tags the same way for both node and way elements

  
    if element.tag == 'node': 
        node_tags = {}
        for field in NODE_FIELDS:
            node_attribs[field] = element.get(field) #storing every k & v of the node into a dictionary
            
        for tag in element.iter("tag"): #nesting inside inner tags of the current node
            
            if re.search(PROBLEMCHARS,tag.get('k')): #if a key has problems in the characters, then ignore it.
                continue
                
            node_tags['id'] = node_attribs.get('id') #store the id of the parent's node into the tag's dictionary. 
            
            if is_street_name(tag):
                node_tags['value'] = update_street_name(tag.attrib['v'])#this method fixes the street name and return it
            elif is_postcode(tag):
                node_tags['value'] = update_postcode(tag.attrib['v'])#this method fixes the postcode and return it
            else:
                node_tags['value'] = tag.get('v')
            
            if re.search(LOWER_COLON,tag.get('k')):
                node_tags['type'] = tag.get('k').split(':')[0]#take the word before the ':' and assign it as as type
                node_tags['key'] = tag.get('k').replace(node_tags['type']+":",'') #assigning the key
                
            else:
                node_tags['type'] = default_tag_type #assign the type as regular
                node_tags['key'] = tag.get('k')
                
            tags.append(node_tags)
            node_tags = {} 
            
        return {'node': node_attribs, 'node_tags': tags}
    
    elif element.tag == 'way':
        position = 0 #works as a counter to count how many references inside the nd tag
        for field in WAY_FIELDS:
            way_attribs[field] = element.get(field)#storing every k & v of the way into a dictionary
            
        for tag in element.iter("nd"):
        
            way_nodes_record['id'] = way_attribs.get('id')
            way_nodes_record['node_id'] = tag.get('ref')
            way_nodes_record['position'] = position
            position +=1
            way_nodes.append(way_nodes_record)
            way_nodes_record = {}
            
        for tag in element.iter("tag"): #the code below works exactly the same as above
            
            if re.search(PROBLEMCHARS,tag.get('k')):
                continue
            
                
            way_tags['id'] = way_attribs.get('id')
            
            if is_street_name(tag):
                way_tags['value'] = update_street_name(tag.attrib['v'])
            elif is_postcode(tag):
                way_tags['value'] = update_postcode(tag.attrib['v'])
            else:
                way_tags['value'] = tag.get('v')
            
            if re.search(LOWER_COLON,tag.get('k')):
                way_tags['type'] = tag.get('k').split(':')[0]
                way_tags['key'] = tag.get('k').replace(way_tags['type']+":",'')
                
            else:
                way_tags['type'] = default_tag_type
                way_tags['key'] = tag.get('k')
                
            tags.append(way_tags)
            way_tags = {}

        
        return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}
    


# ================================================== #
#               Helper Functions                     #
# ================================================== #
street_type_re = re.compile(r'\b\S+\.?$', re.IGNORECASE)



mapping = { "St": "Street",
            "St.": "Street",
            "st" : "Street",
            "Blvd": "Boulevard",
            "Ave.": "Avenue",
            "Ave": "Avenue",
            "AVE": "Avenue",
            "Rd.": "Road",
            "Rd": "Road",
            "PKWY": "Parkway",
            "Pkwy": "Parkway",
            "Ln": "Lane",
            "CT": "Court",
            "Ct": "Court",
            "Cir": "Circle",
            "Cres": "Crescent",
            "Ter": "Terrace",
            "DRIVE": "Drive",
            "STREET": "Street"
            }



def is_street_name(elem): #check if the tag is related to streets/addresses
    return (elem.attrib['k'] == "addr:street")


def update_street_name(name):  
    if street_type_re.search(name):# if the regular expression is met then it is True
        try:
            #True means the street name looks fine.
            if street_type_re.search(name).group() not in mapping.keys(): 
                return fix_digitized_street(name) 
            else:
                #extract the street name that needs to be mapped.
                street_typo = street_type_re.search(name).group()
                #mapping with the dictionary above.
                fixed_street = name.replace(street_typo,mapping.get(street_typo)) 
                return fix_digitized_street(fixed_street)
        except:
            return name
        
def fix_digitized_street(street):  
    #Regular Expressio to search for 1st, 2nd ....
    digitized_street_re = re.compile("\\((?:1ST|2ND|3RD|4TH|5TH|6TH|7TH|8TH|9TH|10TH)\\)|\\b(?:1ST|2ND|3RD|4TH|5TH|6TH|7TH|8TH|9TH|10TH)\\b", re.IGNORECASE)
    #map each digitized street with its corresponding corrected name
    digitized_street_mapping = {
                     "1st": "First",
                     "2nd": "Second",
                     "3rd": "Third",
                     "4th": "Fourth",
                     "5th": "Fifth",
                     "6th": "Sixth",
                     "7th": "Seventh",
                     "8th": "Eighth",
                     "9th": "Ninth",
                     "10th": "Tenth"
                   }
    if digitized_street_re.search(street):
        street_typo = digitized_street_re.search(street).group() #catch the digitized segment
        #lower case the catch since the keys in the mapping are lower-case 
        street_typo = street_typo.lower()
        #mapping with the dictionary above.
        fixed_street = street.replace(street_typo,digitized_street_mapping.get(street_typo))
        return fixed_street
    else:
        return street
        
def is_postcode(elem):#check if the tag is related to postcodes
    return (elem.attrib['k'] in ['addr:postcode', 'postcode' ,'postal_code'])
        
def update_postcode(postcode):
    # will catch any pattern that contains 5 consecutive digits and exclude any leading characters 
    post_code_typo = re.match(r'^\D*(\d{5}).*',postcode)
    if post_code_typo:
        fixed_postcode = post_code_typo.group(1)  #return only the 5 digits (or 4 if any)
        return fixed_postcode

def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag"""

    context = ET.iterparse(osm_file, events=('start', 'end'))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()


def validate_element(element, validator, schema=SCHEMA):
    """Raise ValidationError if element does not match schema"""
    if validator.validate(element, schema) is not True:
        field, errors = next(validator.errors.iteritems())
        message_string = "\nElement of type '{0}' has the following errors:\n{1}"
        error_string = pprint.pformat(errors)
        
        raise Exception(message_string.format(field, error_string))


class UnicodeDictWriter(csv.DictWriter, object):
    """Extend csv.DictWriter to handle Unicode input"""

    def writerow(self, row):
        super(UnicodeDictWriter, self).writerow({
            k: (v.encode('utf-8') if isinstance(v, unicode) else v) for k, v in row.iteritems()
        })

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


# ================================================== #
#               Main Function                        #
# ================================================== #
def process_map(file_in, validate):
    """Iteratively process each XML element and write to csv(s)"""

    with codecs.open(NODES_PATH, 'w') as nodes_file, \
         codecs.open(NODE_TAGS_PATH, 'w') as nodes_tags_file, \
         codecs.open(WAYS_PATH, 'w') as ways_file, \
         codecs.open(WAY_NODES_PATH, 'w') as way_nodes_file, \
         codecs.open(WAY_TAGS_PATH, 'w') as way_tags_file:

        nodes_writer = UnicodeDictWriter(nodes_file, NODE_FIELDS)
        node_tags_writer = UnicodeDictWriter(nodes_tags_file, NODE_TAGS_FIELDS)
        ways_writer = UnicodeDictWriter(ways_file, WAY_FIELDS)
        way_nodes_writer = UnicodeDictWriter(way_nodes_file, WAY_NODES_FIELDS)
        way_tags_writer = UnicodeDictWriter(way_tags_file, WAY_TAGS_FIELDS)

        nodes_writer.writeheader()
        node_tags_writer.writeheader()
        ways_writer.writeheader()
        way_nodes_writer.writeheader()
        way_tags_writer.writeheader()

        validator = cerberus.Validator()

        for element in get_element(file_in, tags=('node', 'way')):
            el = shape_element(element)
            if el:
                if validate is True:
                    validate_element(el, validator)

                if element.tag == 'node':
                    nodes_writer.writerow(el['node'])
                    node_tags_writer.writerows(el['node_tags'])
                elif element.tag == 'way':
                    ways_writer.writerow(el['way'])
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])


if __name__ == '__main__':
    # Note: Validation is ~ 10X slower. For the project consider using a small
    # sample of the map when validating.
    process_map(OSM_PATH, validate=False)
