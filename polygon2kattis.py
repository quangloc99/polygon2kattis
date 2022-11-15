import argparse
import pathlib
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
import shutil

@dataclass
class SupportedLanguage:
    name: str
    short_name: str

ENGLISH_LANG = SupportedLanguage(name='english', short_name='en')
VIETNAMESE_LANG = SupportedLanguage(name='vietnamese', short_name='vn')
SUPPORTED_LANGUAGES=[ENGLISH_LANG, VIETNAMESE_LANG]

SUPPORTED_LANGUAGES_MAP = {}
for lang in SUPPORTED_LANGUAGES:
    SUPPORTED_LANGUAGES_MAP[lang.name] = lang

class Polygon2Kattis:
    def __init__(self, package_zip_file, out_path):
        self.package_zip_file = package_zip_file
        self.package = ZipFile(package_zip_file, 'r')
        self.out_path = out_path
        self.out_path.mkdir(parents=True, exist_ok=True)
        self.problem_data = ET.fromstringlist(self.package.open('problem.xml'))
        
    def extract_package_member_to(self, member, dest):
        print(member, dest)
        with self.package.open(member, 'r') as source, open(dest, 'wb') as target:
            shutil.copyfileobj(source, target)
        
    def process_statement(self, lang: SupportedLanguage):
        print('Processing statement')
        member_name = f'statement-sections/{lang.name}'
        filename_list = [name for name in self.package.namelist() if name.startswith(member_name)]
        
        if len(filename_list) == 0:
            return 
        
        problem_statement_path = self.out_path / 'problem_statement'
        problem_statement_path.mkdir(parents=True, exist_ok=True)
        
        for filename in filename_list:
            dest_path = problem_statement_path / pathlib.Path(filename).name
            if dest_path.suffix == '':
                continue
            self.extract_package_member_to(filename, dest_path)
            # self.package.extract(filename, problem_statement_path)
        
        statement_file_path = problem_statement_path / f'problem.{lang.short_name}.tex'
        with open(statement_file_path, 'w') as out:
            p = problem_statement_path / 'name.tex'
            if p.is_file():
                problem_name = p.read_text().strip()
                print(problem_name)
                print(fr'\problemname{{ {problem_name} }}', file=out)
                p.unlink()
                
            p = problem_statement_path / 'legend.tex'
            if p.is_file():
                print(fr'{p.read_text()}', file=out)
                p.unlink()
                
            p = problem_statement_path / 'input.tex'
            if p.is_file():
                print(r'\section*{Input}', file=out)
                print(fr'{p.read_text()}', file=out)
                p.unlink()
                
            p = problem_statement_path / 'output.tex'
            if p.is_file():
                print(r'\section*{Output}', file=out)
                print(fr'{p.read_text()}', file=out)
                p.unlink()
                
            p = problem_statement_path / 'notes.tex'
            if p.is_file():
                print(r'\section*{Explanation of the sample}', file=out)
                print(fr'{p.read_text()}', file=out)
                p.unlink()
        

argparser = argparse.ArgumentParser(description='Convert a Codeforces.Polygon full package to Kattis problem tool directory')
argparser.add_argument('package',
                       type=argparse.FileType('rb'),
                       # required=True,
                       help='The Codeforces.Polygon FULL package'
                       )
argparser.add_argument('-o', '--out-dir',
                       type=pathlib.Path,
                       required=True,
                       help='The directory for the problem to use with Kattis problem tool'
                       )

def main():
    args = argparser.parse_args()
    # print(args)
    p2k = Polygon2Kattis(args.package, args.out_dir)
    p2k.process_statement(ENGLISH_LANG)
    # p2k.process_statement(VIETNAMESE_LANG)
    # with ZipFile(args.package, 'r') as package:
        # package.printdir()
        # with package.open('problem.xml') as metaData:
            # print(metaData.readlines())
            
main()
