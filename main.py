# -*- coding: utf-8 -*-
import concurrent.futures
import requests , os, collections, argparse
from bs4 import BeautifulSoup
from urllib.parse import unquote



pool = concurrent.futures.ThreadPoolExecutor(max_workers=70)


def parse_args():
    parser = argparse.ArgumentParser(description="downloading moodle files")
    parser.add_argument("username",help= 'your id', type=int)
    parser.add_argument("password",help= 'you digit password', type=int)
    return parser.parse_args()


def main():
    path_root = 'output'
    session = requests.session()
    args = parse_args()
    login(session,args.username,args.password)
    courses = find_all_courses(session)
    for course in courses.keys():
        print(course)
        path = os.path.join(path_root,course)
        course_url = courses[course]
        make_one_course(session,path,course_url)


        
    

def make_one_course(session,path,course_url):
    parsed_files = parse_one_course(session,path, course_url)
    download_from_site(session, parsed_files)
    add_course_html(session, path, parsed_files, course_url)
    


def login(session,username,password):
    payload =  {'username':username,
            'password':password}
    session.post(r'https://moodle.technion.ac.il/login/index.php',data=payload)
    return 


def find_all_courses(session):
    request_output = session.get(r'https://moodle.technion.ac.il')
    bs = BeautifulSoup(request_output.text,'lxml')
    courses_to_links = {course.text : course.a['href'] for course in  bs.find_all('h3')}
    return courses_to_links
        


def parse_one_course(session, origin_path,course_url):
    request_res = session.get(course_url)
    path = collections.defaultdict(str)
    bs = BeautifulSoup(request_res.text,'lxml')
    sections = filter(lambda x: x.h3, bs.find_all('div',{'class' : 'content'}))
    File_obj = collections.namedtuple('File_obj',['url','path','file_name','li_id'])
    files = dict()
    for section in sections:
        section_name = section.find(True,{'class': 'sectionname'})
        if not section_name: continue
        section_name = section_name.contents[0].text
        path['section']  = section_name
        path['subsection'] = ''
        activities = list(section.find_all('li'))
        for activity in activities:
            if 'label' in activity['class']:
                path['subsection'] = activity.get_text()
            elif "resource" in activity['class']:
                link_tag = activity.find('a')
                file_name = link_tag.find(True,{'class': 'instancename'}).contents[0]
                new_path = os.path.join(origin_path,path['section'],path['subsection'])
                initial_file_url = activity.find('a')['href']
                file_url = pool.submit(find_file_url_from_link,session,initial_file_url)
                file_obj = File_obj(file_url,new_path,file_name,activity['id'])
                files[file_url] = file_obj
    return files




def find_file_url_from_link(session,url_link):
    request_output = session.get(url_link)
    bs = BeautifulSoup(request_output.content,'lxml')
    added = bs.find('iframe')
    if added:  return added['src']
    embeded = bs.find('param',{'name': 'src'})
    if embeded: return embeded['value']
    workaround = bs.find(True,{'class': 'resourceworkaround'})
    if workaround: return workaround.a['href']
    if request_output.history: return request_output.url
    else:
        raise FileNotFoundError("couldn't parse this link '{}'".format(url_link))



def add_course_html(session,path,files,course_url):
    os.makedirs(path, exist_ok=True)
    request_output = session.get(course_url)
    bs = BeautifulSoup(request_output.content,'lxml')
    for file in files.values():
        li = bs.find("li",{"id":file.li_id})
        link = li.find("a")
        relpath_dirname = os.path.relpath(file.path,path)
        file_name = os.path.basename(unquote(file.url.result()))
        relpath = os.path.join(relpath_dirname,file_name)
        link['onclick'] = relpath
        link['href'] = relpath
        link['style'] = "color:brown"
    with open(os.path.join(path,"moodle.html"),"wb") as fd:
        fd.write(bs.prettify('utf-8'))
    
        
def download_from_site(session,files):
    for file in concurrent.futures.as_completed(files):
        file_obj = files[file]
        print(file_obj.file_name)
        dirname = os.path.realpath(file_obj.path)
        os.makedirs(dirname, exist_ok=True)
        filename= os.path.basename(file_obj.url.result())
        new_path = unquote(os.path.join(dirname,filename))
        with open(new_path.replace("?",""), "wb") as f:
            content = session.get(file_obj.url.result(),stream=True).raw.data
            f.write(content)


if __name__ == "__main__":
    main()