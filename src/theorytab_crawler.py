import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import os
import time
import json
import re
import string

website = 'https://www.hooktheory.com'
base_url = website + '/theorytab/artists/'
sleep_time = 0.11
# alphabet_list = string.ascii_lowercase
alphabet_list = 'qrstuvwxyz'
root_dir = '../datasets'
root_xml = '../datasets/xml'


def song_retrieval(artist, song, path_song):
    suffix = '/theorytab/view/' + artist + '/' + song
    song_url = song_url = 'https://www.hooktheory.com' + suffix
    response_song = requests.get(song_url)

    soup = BeautifulSoup(response_song.text, 'html.parser')

    section_list = [item['href'].split('#')[-1] for item in soup.find_all('a', {'href': re.compile(suffix+'#')})]
    tab_list = soup.find_all('div', {'id': re.compile("tab-")})
    pk_list = [item.get('id').split('-')[-1] for item in tab_list]
    # save xml
    for idx, pk in enumerate(pk_list):
        req_url = 'https://www.hooktheory.com/songs/getXmlByPk?pk=' + str(pk)
        response_info = requests.get(req_url)
        content = response_info.text
        with open(os.path.join(path_song, section_list[idx] + ".xml"), "w", encoding="utf-8") as f:
            f.write(content)
        time.sleep(0.08)

    # get genre
    wikiid = soup.findAll("multiselect", {"items": "genres"})[0]['wikiid']
    response_genre = requests.get('https://www.hooktheory.com/wiki/' + str(wikiid) + '/genres')
    genre_act_list = json.loads(response_genre.text)
    genres = []
    for g in genre_act_list:
        if g['active']:
            genres.append(g['name'])

    # saving
    info = {'section': section_list, 'pk': pk_list, 'song_url': song_url,
            'genres': genres, 'wikiid': wikiid}

    with open(os.path.join(path_song, 'song_info.json'), "w") as f:
        json.dump(info, f)
    return artist, song, path_song

def get_song_list(url_artist):
    artist_name = url_artist.split('/')[-1]
    response_tmp = requests.get(website + url_artist)
    soup = BeautifulSoup(response_tmp.text, 'html.parser')
    item_list = soup.find_all("li", {"class": re.compile("overlay-trigger")})

    song_name_list = []
    for item in item_list:
        song_name = item.find_all("a", {"class": "a-no-decoration"})[0]['href'].split('/')[-1]
        song_name_list.append(song_name)
    return artist_name, song_name_list

def traverse_website():
    '''
    Retrieve all urls of artists and songs from the website
    '''

    list_pages = []
    archive_artist = dict()
    artist_count = 0
    song_count = 0

    for ch in alphabet_list:
        url = base_url + ch
        response_tmp = requests.get(url)
        soup = BeautifulSoup(response_tmp.text, 'html.parser')
        page_count = 0

        print('==[%c]=================================================' % ch)

        # get artists list by pages
        url_artist_list = []
        for page in range(1, 9999):
            url = 'https://www.hooktheory.com/theorytab/artists/'+ch+'?page=' + str(page)
            print(url)
            response_tmp = requests.get(url)
            soup = BeautifulSoup(response_tmp.text, 'html.parser')
            item_list = soup.find_all("li", {"class": re.compile("overlay-trigger")})

            if item_list:
                page_count += 1
            else:
                break

            for item in item_list:
                url_artist_list.append(item.find_all("a", {"class": "a-no-decoration"})[0]['href'])

        print('Total:', len(url_artist_list))

        print('----')

        if not page_count:
            page_count = 1

        # get song of artists
        artist_song_dict = dict()
        
        def artist_song_map(url_artist):
            try: return get_song_list(url_artist)
            except Exception as e:
                print('Error:', url_artist, e)
                return None, None
            
        with ThreadPoolExecutor(max_workers=10) as executor:
            for url_artist, song_name_list in executor.map(artist_song_map, url_artist_list):
                if url_artist is None: continue
                artist_count += 1
                song_count += len(song_name_list)
                artist_name = url_artist.split('/')[-1]
                artist_song_dict[artist_name] = song_name_list
                
                print(artist_name)
                print('   > ' + '\n   > '.join(song_name_list))
            
        archive_artist[ch] = artist_song_dict
        list_pages.append(page_count)

    print('=======================================================')
    print(list_pages)
    print('Artists:', artist_count)
    print('Songs:', song_count)

    archive_artist['num_song'] = song_count
    archive_artist['num_artist'] = artist_count

    return archive_artist


if __name__ == '__main__':

    if not os.path.exists(root_dir):
        os.makedirs(root_dir)

    if not os.path.exists(root_xml):
        os.makedirs(root_xml)

    path_artists = os.path.join(root_dir, 'archive_artist.json')
    
    archive_artist = traverse_website()
    
    # Merge old json
    if os.path.exists(root_xml):
        with open(path_artists, "r") as f:
            archive_artist = {**json.load(f), **archive_artist}
    
    with open(path_artists, "w") as f:
        json.dump(archive_artist, f)

    with open(path_artists, "r") as f:
        archive_artist = json.load(f)

    song_count = archive_artist['num_song']


    for ch in alphabet_list:
        path_ch = os.path.join(root_xml, ch)
        print('==[%c]=================================================' % ch)

        if not os.path.exists(path_ch):
            os.makedirs(path_ch)

        songs = []
        for a_name, s_list in archive_artist[ch].items():
            for s_name in s_list:
                path_song = os.path.join(path_ch, a_name, s_name)
                if os.path.exists(path_song): continue
                songs.append((a_name, s_name, path_song))

        def song_map(args):
            os.makedirs(args[-1], exist_ok=True)
            try: return song_retrieval(*args)
            except Exception as e:
                print('Error:', args, e)
                return None, None, None

        with ThreadPoolExecutor(max_workers=10) as executor:
            for idx, (artist, song, path_song) in enumerate(executor.map(song_map, songs)):
                if artist is None: continue
                print('(%3d/%3d) %s   %s' % (idx, len(songs), artist, song))