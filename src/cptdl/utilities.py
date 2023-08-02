"""
A module to support the creation of ingrid URLs from templates
and loading of data using those URLs 

Several functions accept kwargs. Some of these are common to all
types of downloads and others are specific to the download type
and/or function 

    filetype: File format to save as. Must be 'cptv10.tsv' or 'data.nc', 
              Required for download and evaluate_url functions 
    fdate: date of forecast as datetime object e.g. dt.datetime.now()
    first_year: integer with first year of data to retrieve e.g. 1982
    final_year:  integer with final year of data to retrieve e.g.2018, 
    predictor_extent: dictionary to define spatial extent of predictor data e.g.
      { 'east': 90, 'west': 0, 'north': 90, 'south': 0}, 
    predictand_extent: as predictor_extent but for predictand data (observations)
    lead_low(float): lower value for lead time in months (forecasts and hindcasts) e.g. 1.5
    lead_high(float): higher value for lead time in months (forecasts and hindcasts) e.g. 3.5
    target(str): Target period for forecast e.g.  'Jul-Sep'
    pressure: pressure level for UA and VA only (units?)

optional:
    ensemblemean(:obj:`str`, default True): whether to download ensemble mean (True) or members (False)

"""
from pathlib import Path 
import json, getpass, requests, sys
import datetime as dt 
import xarray as xr 
import cptio as cio 

def read_dlauth():
    """Read IRIDLAUTH file and return authorization key if already set up"""
    if not (Path.home().absolute() / '.pycpt_dlauth').is_file():
        print('You need to set up an IRIDLAUTH! Please set up an IRI account here (https://iridl.ldeo.columbia.edu/auth/signup), then use cptdl.setup_dlauth("your_iri_login_email") to setup the cookie. This only needs to happen once!  ')
        return None
    else: 
        try:
            with open(str(Path.home().absolute() / '.pycpt_dlauth'), 'rb') as f: 
                auth_dict = json.loads(f.read())
            return auth_dict['key']
        except Exception as e: 
            try:
                with open(str(Path.home().absolute() / '.pycpt_dlauth'), 'r') as f: 
                    file = f.read()
                if 'html' in file: 
                    print("Your existing ~/.pycpt_dlauth file looked like an 'incorrect username/password' message!")
                    return None
            except: 
                print('Unable to read text from ~/.pycpt_dlauth - it might be binary spaghetti; broken download? delete it and set up again!')
                return None 


def s2s_login(email):
    pswd = getpass.getpass('DLAUTH PASSWORD: ').strip()
    redirect = "/SOURCES/.ECMWF/.S2S/.NCEP/.forecast/.perturbed/.sfc_temperature/.skt/datafiles.html"
    with requests.Session() as s: 
        r = s.post("https://iridl.ldeo.columbia.edu/auth/login/local/submit/login", data={'email': email, 'password':pswd, 'redirect': redirect})
        r.raise_for_status()
        # in the line below, the two spaces between 'has' and 'bytes' is intentional

        if "This dataset has  bytes" not in r.content.decode('utf-8'):
            print( 'Incorrect user or password'  )
            print(r.content.decode('utf-8'))
        else:
            print('You have recorded your agreement to: the S2S terms and conditions / privacy policy\nT&C: https://iridl.ldeo.columbia.edu/auth/legal/terms-of-service\nPrivacy: https://iridl.ldeo.columbia.edu/auth/legal/privacy-policy')

def c3s_login(email):
    pswd = getpass.getpass('DLAUTH PASSWORD: ').strip()
    redirect ="/SOURCES/.EU/.Copernicus/.CDS/.C3S/.DWD/.GCFS2p1/.hindcast/.prcp/datafiles.html"
    with requests.Session() as s: 
        r = s.post("https://iridl.ldeo.columbia.edu/auth/login/local/submit/login", data={'email': email, 'password':pswd, 'redirect': redirect})
        r.raise_for_status()
        # in the line below, the two spaces between 'has' and 'bytes' is intentional
        if "This dataset has  bytes" not in r.content.decode('utf-8'):
            print( 'Incorrect user or password' )
        else:
            print('You have recorded your agreement to: the C3S terms and conditions / privacy policy\nT&C: https://iridl.ldeo.columbia.edu/auth/legal/terms-of-service\nPrivacy: https://iridl.ldeo.columbia.edu/auth/legal/privacy-policy')


def setup_dlauth(email):
    """
    set up DLAuth with cptdl by making an account at https://iridl.ldeo.columbia.edu/auth/signup
    and then passing the email and password you set up to this function

    Key is saved in IRIDLAUTH and just read on subsequent execution

    Returns:
        authorization key

    Example:
        cptdl.setup_dlauth("pycpt.dev@gmail.com")
        PASSWORD: [enter your password here- it will be invisible] 
    """
    if not (Path.home().absolute() / '.pycpt_dlauth').is_file():
        pswd = getpass.getpass('DLAUTH PASSWORD: ').strip()
        with requests.Session() as s:
            response = s.post("https://iridl.ldeo.columbia.edu/auth/login/local/submit/login", data={'email': email, 'password':pswd, "redirect": "https://iridl.ldeo.columbia.edu/auth"})
            response.raise_for_status()  
            response = s.get("https://iridl.ldeo.columbia.edu/auth/genkey")
            response.raise_for_status()  
            if 'html' in  response.content.decode('utf-8'):
                print('Incorrect Username or Password')
                return None
            with open(str((Path.home().absolute() / '.pycpt_dlauth')), 'wb') as f: 
                f.write(response.content)
    else: 
        print('You already have an IRIDLAUTH (~/.pycpt_dlauth)!')
        return read_dlauth()
        

class PyCPT_ERROR(Exception):
    """PyCPT Exception subclassing Exception"""
    pass    

def evaluate_url(url, ensemblemean=True, **kwargs):
    """
    cptdl.evaluate_url accepts arbitrary keyword arguments, and 
    inserts them dynamically into the url template provided as 
    the first positional argument, url.

    Args:
        url(:obj:`str`): The URL to download from.
        ensemblemean(:obj:`str`): whether to download ensemble mean (True) or members (False)
        See module docstring for kwargs

    Example:
        formatted_url = cptdl.evaluate_url(url, predictor_extent={'east':130, ...}, ... )
    """
    from .targetleadconv import seasonal_target, seasonal_target_length_monthly, seasonal_target_length, threeletters
    locals().update(**kwargs)
    return eval('f"{}"'.format(url))


def simple_download(url, dest, verbose=False, use_dlauth=False):
    """
    downloads the provided url to the provided destination file path
    unlike using curl won't download 404 not-found messages

    Args:
        url(:obj:`str`): The URL to download from.
        dest(:obj:`str`): The location to download to.
        verbose(bool, optional): if True show a progress bar for the download, defaults to False
        use_dlauth(bool, optional): if True will attempt to read ~/.pycpt_dlauth 
            and pass it as a cookie in the request to the URL, defaults to False.

    Returns:
        path(:obj:`str`): the full location of the download

    Example:

        import cptdl as dl 
        docspage = dl.simple_download(
            "https://raw.githubusercontent.com/kjhall-iri/cpt-dl/master/src/utilities.py", 
            "/Path/To/Destination/utilities/py") 
    """
    if verbose:
        print('URL: {}'.format(url))
        print()
    if str(use_dlauth) == 'True':
        dlauthid = read_dlauth()
        assert dlauthid is not None, "You need to use cpttools.setup_dlauth('your_email') to get a cookie before you can download this data! or, you can try setting use_dlauth=False"
        cookies = {'__dlauth_id': dlauthid}
    else:
        cookies={}
    with requests.post(url, stream=True, allow_redirects=True, cookies=cookies) as r:
        r.raise_for_status()  
        path = Path(dest).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        start, j, total_size = dt.datetime.now(), 0, 0
        if verbose:
            print('DOWNLOADING: [' + ' ' * 25 + '] ({} KB) {}'.format(total_size // 1000, dt.datetime.now() - start), end='\r')
        with path.open("wb") as f:
            for chunk in r.iter_content(16*1024):
                j += 1
                total_size += sys.getsizeof(chunk)
                if verbose:
                    print('\rDOWNLOADING: [' + '*'*j + ' ' * (25 -j ) + '] ({} KB) {}'.format(total_size // 1000, dt.datetime.now() - start), end='\r')
                j = 0 if j >= 25 else j
                f.write(chunk)
        if verbose:
            print('DOWNLOADING: [' + '*' * 25 + '] ({} KB) {}'.format(total_size // 1000, dt.datetime.now() - start))
    assert path.is_file(), 'failed to write file'
    return path 


def download(baseurl, dest, verbose=False, use_dlauth=True, **kwargs):
    """
    convenience function thats combines
    the evaluation of a template URL
    the download of the file
    opening of that file with cptio

    Args:
        baseurl(:obj:`str`): The URL template 
        dest(:obj:`str`): The location to download to.
        verbose(bool, optional): if True show a progress bar for the download, defaults to False
        use_dlauth(bool, optional): if True will attempt to read ~/.pycpt_dlauth 
            and pass it as a cookie in the request to the URL, defaults to False.
        kwargs: see module docstring
    
    Example:
        dataarray = cptdl.download(url, destfile, **kwargs) which returns an Xarray.DataArray
    """
    if 'filetype' in kwargs.keys():
        format = kwargs['filetype']
    else: 
        raise PyCPT_ERROR("Required keyword argument missing: 'filetype'")
    assert format in ['cptv10.tsv', 'data.nc'], 'invalid download format: {}'.format(format)
    try:
        url = evaluate_url(baseurl, **kwargs)
    except:
        raise PyCPT_ERROR("You must pass all the required arguments for this URL as keyword arguments in .download(...). \n URL: {}\n ARGS: {}".format(baseurl, kwargs))

    path = simple_download(url, dest, verbose=verbose, use_dlauth=use_dlauth)
    
    try: 
        ds = cio.open_cptdataset(path) if format == 'cptv10.tsv' else xr.open_dataset(path, decode_times=False) 
    except Exception as e: 
            raise PyCPT_ERROR("Please check what's downloaded from here, it may be a broken: {}".format(url))
    return ds 

