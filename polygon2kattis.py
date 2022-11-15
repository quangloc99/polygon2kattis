import argparse
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
import shutil

@dataclass
class SupportedLanguage:
    name: str
    short_name: str
    
    def __str__(self):
        return self.short_name

ENGLISH_LANG = SupportedLanguage(name='english', short_name='en')
VIETNAMESE_LANG = SupportedLanguage(name='vietnamese', short_name='vn')
SUPPORTED_LANGUAGES=[ENGLISH_LANG, VIETNAMESE_LANG]

def get_lang(short_name):
    for lang in SUPPORTED_LANGUAGES:
        if lang.short_name == short_name:
            return lang
    raise TypeError(f'{short_name} is not a supported language')
    
def build_argparser():
    argparser = argparse.ArgumentParser(description='Convert a Codeforces.Polygon full package to Kattis problem tool directory')
    argparser.add_argument('package',
                           type=argparse.FileType('rb'),
                           # required=True,
                           help='The Codeforces.Polygon FULL package'
                           )
    argparser.add_argument('-o', '--out-dir',
                           type=Path,
                           required=True,
                           help='The directory for the problem to use with Kattis problem tool'
                           )
    argparser.add_argument('--lang',
                           choices=SUPPORTED_LANGUAGES,
                           type=get_lang,
                           help='The chosen language to generate. The default is `en` (for English)',
                           default='en'
                           )
    argparser.add_argument('-v', '--verbose',
                           action='store_true',
                           help='Print more messages for debugging purposes'
                           )
    return argparser


class Polygon2Kattis:
    def __init__(self, package_zip_file, out_path: Path, lang: SupportedLanguage, verbose: bool):
        self.package_zip_file = package_zip_file
        self.package = ZipFile(package_zip_file, 'r')
        self.lang = lang
        self.verbose = verbose
        self.problem_data = ET.fromstringlist(self.package.open('problem.xml'))
        self.testlib_path = Path(__file__).parent / 'testlib.h'
        
        self.out_path = self.force_mkdir(out_path)
        
        self.problem_statement_path = self.add_folder(self.out_path, 'problem_statement')
        self.data_path = self.add_folder(self.out_path, 'data')
        self.sample_data_path = self.add_folder(self.data_path, 'sample')
        self.secret_data_path = self.add_folder(self.data_path, 'secret')
        
        self.check_type = ''
        
    def force_mkdir(self, path):
        path.mkdir(parents=True, exist_ok=True)
        return path
        
    def add_folder(self, path, *subfolders):
        for subfolder in subfolders:
            path = self.force_mkdir(path / subfolder)
        return path
        
    def log(self, *args):
        if self.verbose:
            print(*args)
        
    def extract_package_member_to(self, member, dest):
        self.log('extracting', member, dest)
        with self.package.open(member, 'r') as source, open(dest, 'wb') as target:
            shutil.copyfileobj(source, target)
        
    def process_statement(self):
        self.log('Processing statement')
        member_name = f'statement-sections/{self.lang.name}'
        filename_list = [name for name in self.package.namelist() if name.startswith(member_name)]
        
        if len(filename_list) == 0:
            return 
        
        for filename in filename_list:
            dest_path = self.problem_statement_path / Path(filename).name
            if dest_path.suffix == '':
                continue
            self.extract_package_member_to(filename, dest_path)
            # self.package.extract(filename, self.problem_statement_path)
        
        statement_file_path = self.problem_statement_path / f'problem.{self.lang.short_name}.tex'
        with open(statement_file_path, 'w') as out:
            p = self.problem_statement_path / 'name.tex'
            if p.is_file():
                problem_name = p.read_text().strip()
                print(problem_name)
                print(fr'\problemname{{ {problem_name} }}', file=out)
                p.unlink()
                
            p = self.problem_statement_path / 'legend.tex'
            if p.is_file():
                print(p.read_text(), file=out)
                p.unlink()
                
            p = self.problem_statement_path / 'input.tex'
            if p.is_file():
                print(r'\section*{Input}', file=out)
                print(p.read_text(), file=out)
                p.unlink()
                
            p = self.problem_statement_path / 'output.tex'
            if p.is_file():
                print(r'\section*{Output}', file=out)
                print(p.read_text(), file=out)
                p.unlink()
                
            p = self.problem_statement_path / 'notes.tex'
            if p.is_file():
                print(r'\section*{Explanation of the sample}', file=out)
                print(p.read_text(), file=out)
                p.unlink()
                
            p = self.problem_statement_path / 'scoring.tex'
            if p.is_file():
                print(r'\section*{Scoring}', file=out)
                print(p.read_text(), file=out)
                p.unlink()
                
    def process_tests(self):
        self.log('Processing tests')
        testsets = self.problem_data.findall('./judging/testset')
        for testset in testsets:
            self.process_testset(testset)
        
    def process_testset(self, testset):
        testset_name = testset.get('name')
        self.log('Processing testset', testset_name)
        
        cur_sample_data_path = self.sample_data_path
        cur_secret_data_path = self.add_folder(self.secret_data_path, testset_name)
        
        input_path_pattern = testset.find('input-path-pattern').text
        answer_path_pattern = testset.find('answer-path-pattern').text
        testcount = int(testset.find('test-count').text)
        test_tags = testset.findall('./tests/test')
        
        for test_id in range(1, testcount + 1):
            input_filename = input_path_pattern % test_id
            answer_filename = answer_path_pattern % test_id
            test_tag = test_tags[test_id - 1]
            is_sample = test_tag.get('sample') == 'true'
            
            dest_path = cur_sample_data_path if is_sample else cur_secret_data_path
            self.extract_package_member_to(input_filename, dest_path / f'{test_id}.in')
            self.extract_package_member_to(input_filename, dest_path / f'{test_id}.ans')
            
    def process_solutions(self):
        self.log('Processing solutions')
        solution_tags = self.problem_data.findall('./assets/solutions/solution')
        submission_path = self.out_path / 'submissions'
        for solution_tag in solution_tags:
            tag = solution_tag.get('tag')
            path = solution_tag.find('source').get('path')
            if tag in ['accepted', 'main']:
                sol_out_path = self.add_folder(submission_path, 'accepted')
            elif tag == 'time-limit-exceeded':
                sol_out_path = self.add_folder(submission_path, 'time_limit_exceed')
            elif tag == 'wrong-answer':
                sol_out_path = self.add_folder(submission_path, 'wrong_answer')
            else:
                self.log('Skip solution', path, f'of tag {tag}')
                continue
            self.extract_package_member_to(path, sol_out_path / Path(path).name)
            
    def process_checker_validator_interactor(self):
        self._process_checker()
        self._process_validator()
        
    def _process_checker(self):
        checker_tags = self.problem_data.findall('./assets//checker')
        if len(checker_tags) == 0:
            return 
        checker_tag = checker_tags[0]
        checker_name = checker_tag.get('name')
        if checker_name is not None:
            self.checker_type = checker_name
            return 
        else:
            self.checker_type = 'custom'
        source_tag = checker_tag.find('source')
        source_path = source_tag.get('path')
        checker_out_dir = self.add_folder(self.out_path, 'output_validators', 'checker')
        self.extract_package_member_to(source_path, checker_out_dir / Path(source_path).name)
        if 'cpp' in source_tag.get('type'):
            shutil.copy(self.testlib_path, checker_out_dir)
    
    def _process_validator(self):
        validator_tags = self.problem_data.findall('./assets/validators/validator')
        if len(validator_tags) == 0:
            return
        validator_tag = validator_tags[0]
        source_tag = validator_tag.find('source')
        source_path = source_tag.get('path')
        validator_out_dir = self.add_folder(self.out_path, 'input_validators', 'extracted_validator')
        self.extract_package_member_to(source_path, validator_out_dir / Path(source_path).name)
        if 'cpp' in source_tag.get('type'):
            shutil.copy(self.testlib_path, validator_out_dir)
            
    def _process_interactor(self):
        # TODO
        pass

def main():
    args = build_argparser().parse_args()
    print(args)
    p2k = Polygon2Kattis(args.package, args.out_dir, args.lang, args.verbose)
    p2k.process_statement()
    # p2k.process_tests()
    p2k.process_solutions()
    p2k.process_checker_validator_interactor()
    
    p2k.log('done')
            
main()
