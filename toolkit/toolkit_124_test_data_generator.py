"""toolkit_124_test_data_generator.py
Generate realistic fake test data — names, addresses, emails, credit cards, etc.
"""
import random
import string
import re
import json
import uuid
import datetime
import hashlib

try:
    from faker import Faker; _FAKER = Faker(); HAS_FAKER = True
except ImportError:
    _FAKER = None; HAS_FAKER = False

_FIRST_NAMES = ['Alice','Bob','Charlie','Diana','Eve','Frank','Grace','Henry','Iris','Jack','Kate','Liam','Mia','Noah','Olivia','Paul','Quinn','Rachel','Sam','Tara','Uma','Victor','Wendy','Xavier','Yara','Zane']
_LAST_NAMES = ['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis','Wilson','Taylor','Anderson','Thomas','Jackson','White','Harris','Martin','Thompson','Young','Robinson','Lewis']
_DOMAINS = ['gmail.com','yahoo.com','hotmail.com','outlook.com','example.com','test.org']
_STREETS = ['Main St','Oak Ave','Pine Rd','Maple Dr','Cedar Ln','Elm Way','Birch Blvd','Walnut St','Ash Ct','Poplar Dr']
_CITIES = ['New York','Los Angeles','Chicago','Houston','Phoenix','Philadelphia','San Antonio','San Diego','Dallas','San Jose']
_STATES = ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY']
_COMPANIES = ['Acme Corp','Globex','Initech','Umbrella Corp','Hooli','Pied Piper','Dunder Mifflin','Vandelay Industries','Soylent Corp','Weyland-Yutani']
_TLDS = ['.com','.org','.net','.io','.co','.dev','.app']

def fake_name() -> dict:
    """Generate a random full name."""
    try:
        if HAS_FAKER: return {'success': True, 'data': _FAKER.name(), 'error': None}
        first = random.choice(_FIRST_NAMES)
        last = random.choice(_LAST_NAMES)
        return {'success': True, 'data': first + ' ' + last, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def fake_email(name: str = '') -> dict:
    """Generate a random email address."""
    try:
        if HAS_FAKER: return {'success': True, 'data': _FAKER.email(), 'error': None}
        if not name:
            name = random.choice(_FIRST_NAMES) + random.choice(_LAST_NAMES)
        local = re.sub(r'[^a-zA-Z0-9]', '', name.lower()) + str(random.randint(1, 999))
        domain = random.choice(_DOMAINS)
        return {'success': True, 'data': local + '@' + domain, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def fake_phone(format_str: str = 'us') -> dict:
    """Generate a fake phone number."""
    try:
        if HAS_FAKER: return {'success': True, 'data': _FAKER.phone_number(), 'error': None}
        area = str(random.randint(200, 999))
        exchange = str(random.randint(200, 999))
        number = str(random.randint(1000, 9999))
        return {'success': True, 'data': '(' + area + ') ' + exchange + '-' + number, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def fake_address() -> dict:
    """Generate a fake street address."""
    try:
        if HAS_FAKER: return {'success': True, 'data': {'street': _FAKER.street_address(), 'city': _FAKER.city(), 'state': _FAKER.state_abbr(), 'zip': _FAKER.zipcode()}, 'error': None}
        number = str(random.randint(100, 9999))
        street = random.choice(_STREETS)
        city = random.choice(_CITIES)
        state = random.choice(_STATES)
        zipcode = str(random.randint(10000, 99999))
        return {'success': True, 'data': {'street': number + ' ' + street, 'city': city, 'state': state, 'zip': zipcode, 'full': number + ' ' + street + ', ' + city + ', ' + state + ' ' + zipcode}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def fake_company() -> dict:
    """Generate a fake company name."""
    try:
        if HAS_FAKER: return {'success': True, 'data': _FAKER.company(), 'error': None}
        return {'success': True, 'data': random.choice(_COMPANIES), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def fake_url() -> dict:
    """Generate a fake URL."""
    try:
        if HAS_FAKER: return {'success': True, 'data': _FAKER.url(), 'error': None}
        sub = ''.join(random.choices(string.ascii_lowercase, k=random.randint(4,8)))
        tld = random.choice(_TLDS)
        path = '/'.join(''.join(random.choices(string.ascii_lowercase, k=4)) for _ in range(random.randint(0,2)))
        return {'success': True, 'data': 'https://' + sub + tld + ('/' + path if path else ''), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def fake_uuid() -> dict:
    """Generate a random UUID."""
    try:
        return {'success': True, 'data': str(uuid.uuid4()), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def fake_date(start_year: int = 1980, end_year: int = 2024) -> dict:
    """Generate a random date."""
    try:
        start = datetime.date(start_year, 1, 1)
        end = datetime.date(end_year, 12, 31)
        delta = (end - start).days
        random_days = random.randint(0, delta)
        d = start + datetime.timedelta(days=random_days)
        return {'success': True, 'data': d.isoformat(), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def fake_credit_card() -> dict:
    """Generate a fake (Luhn-valid) credit card number."""
    try:
        def luhn_checksum(card_num):
            digits = [int(d) for d in card_num]
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(divmod(d * 2, 10))
            return checksum % 10
        def generate_luhn(prefix, length):
            number = [int(d) for d in prefix]
            while len(number) < length - 1:
                number.append(random.randint(0, 9))
            number.append(0)
            check = (10 - luhn_checksum(''.join(map(str, number)))) % 10
            number[-1] = check
            return ''.join(map(str, number))
        card_types = [('Visa', '4', 16), ('MasterCard', '5' + str(random.randint(1,5)), 16), ('Amex', '37', 15)]
        card_type, prefix, length = random.choice(card_types)
        number = generate_luhn(prefix, length)
        expiry = str(random.randint(1,12)).zfill(2) + '/' + str(random.randint(25,30))
        cvv = ''.join([str(random.randint(0,9)) for _ in range(3)])
        return {'success': True, 'data': {'type': card_type, 'number': number, 'expiry': expiry, 'cvv': cvv, 'note': 'FAKE - for testing only'}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def fake_person() -> dict:
    """Generate a full fake person record."""
    try:
        name_result = fake_name()
        name = name_result['data']
        return {'success': True, 'data': {'name': name, 'email': fake_email(name.replace(' ',''))['data'], 'phone': fake_phone()['data'], 'address': fake_address()['data'], 'company': fake_company()['data'], 'dob': fake_date(1960, 2000)['data'], 'id': str(uuid.uuid4())[:8]}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_dataset(count: int = 10, record_type: str = 'person') -> dict:
    """Generate a list of fake records. record_type: person, address, company."""
    try:
        generators = {'person': fake_person, 'address': fake_address, 'company': fake_company, 'email': fake_email, 'name': fake_name, 'phone': fake_phone}
        gen = generators.get(record_type, fake_person)
        records = [gen()['data'] for _ in range(count)]
        return {'success': True, 'data': records, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def fake_password(length: int = 16, include_symbols: bool = True) -> dict:
    """Generate a random password."""
    try:
        chars = string.ascii_letters + string.digits
        if include_symbols: chars += '!@#$%^&*()'
        password = ''.join(random.choices(chars, k=length))
        return {'success': True, 'data': password, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def fake_lorem(sentences: int = 3) -> dict:
    """Generate fake lorem ipsum text."""
    try:
        if HAS_FAKER: return {'success': True, 'data': _FAKER.paragraph(nb_sentences=sentences), 'error': None}
        words = ['lorem','ipsum','dolor','sit','amet','consectetur','adipiscing','elit','sed','do','eiusmod','tempor','incididunt','ut','labore','et','dolore','magna','aliqua','ut','enim','ad','minim','veniam','quis','nostrud','exercitation','ullamco','laboris']
        result_sentences = []
        for _ in range(sentences):
            num_words = random.randint(8, 15)
            sentence = ' '.join(random.choices(words, k=num_words))
            result_sentences.append(sentence.capitalize() + '.')
        return {'success': True, 'data': ' '.join(result_sentences), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
