# -*- coding: utf-8 -*-
import requests , os, collections, sys
from bs4 import BeautifulSoup
from urllib.parse import unquote

username = sys.argv[0]
password = sys.argv[1]


def main():
    path_root = 'output'
    session = requests.session()
    login(session,username,password)
    courses = find_all_courses(session)
    for course in courses.keys():
        print(course)
        path = os.path.join(path_root,course)
        course_url = courses[course]
        make_one_course(session,path,course_url)
        
    

def make_one_course(session,path,course_url):
    parsed_files = parse_one_course(session,path, course_url)
    download_from_site(session, parsed_files)
    add_course_data(session, path, parsed_files, course_url)
    


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
    files = list()
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
                file_url = find_file_url_from_link(session,initial_file_url)
                file_obj = File_obj(file_url,new_path,file_name,activity['id'])
                files.append(file_obj)
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



def add_course_data(session,path,files,course_url):
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path,"mapping.txt"),"w") as fd:
        fd.write(make_mapping_file(files))
    with open(os.path.join(path,"moodle.html"),"wb") as fd:
        fd.write(make_html_snapshot(path,session, course_url,files))



def make_mapping_file(files):
    webName2urlName = {file.file_name : os.path.basename(file.url) for file in files}
    mapping_str = "\n".join(["{:<80} {} ".format(x.strip(),y.strip()) for (x,y) in webName2urlName.items()])
    return mapping_str


def make_html_snapshot(path,session,course_url,files):
    request_output = session.get(course_url)
    bs = BeautifulSoup(request_output.content,'lxml')
    for file in files:
        li = bs.find("li",{"id":file.li_id})
        link = li.find("a")
        relpath_dirname = os.path.relpath(file.path,path)
        file_name = os.path.basename(unquote(file.url))
        relpath = os.path.join(relpath_dirname,file_name)
        link['onclick'] = relpath
        link['href'] = relpath
        link['style'] = "color:brown"
    return bs.prettify('utf-8')
    
        
def download_from_site(session,files):
    for file in files:
        print(file.file_name)
        dirname = os.path.realpath(file.path)
        os.makedirs(dirname, exist_ok=True)
        filename= os.path.basename(file.url)
        new_path = unquote(os.path.join(dirname,filename))
        with open(new_path.replace("?",""), "wb") as f:
            content = session.get(file.url,stream=True).raw.data
            f.write(content)


if __name__ == "__main__":
    main()