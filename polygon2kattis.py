import argparse
import shutil
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile


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
    argparser.add_argument('--write-problem-yaml',
                           action='store_true',
                           help='Write the problem.yaml file. Default is off, to not overwrite the existing problem.yaml'
                           )
    argparser.add_argument('--license',
                           choices=['unknown', 'public domain', 'cc0', 'cc by', 'cc by-sa', 'educational', 'permission'],
                           help='Problem license',
                           default='cc by-sa'
                           )
    argparser.add_argument('--test-generation-info',
                           action='store_true',
                           help=textwrap.dedent("""
                           Generate information about test generation, for the purpose of reviewing:
                           the generators will be copied,
                           and the test generation script will be generated.
                           All the generated and copied file will be in the data folder.
                           """),
                           default=False
                           )
    return argparser


class Polygon2Kattis:
    def __init__(self,
                 package_zip_file,
                 out_dir: Path,
                 lang: SupportedLanguage,
                 verbose: bool,
                 test_generation_info: bool,
                 license: str
                 ):
        self.package_zip_file = package_zip_file
        self.package = ZipFile(package_zip_file, 'r')
        self.lang = lang
        self.verbose = verbose
        self.test_generation_info = test_generation_info

        self.problem_data = ET.fromstringlist(self.package.read('problem.xml').decode())
        self.testlib_path = Path(__file__).parent / 'testlib.h'
        self.license = license
        
        self.out_dir = self.force_mkdir(out_dir)
        
        self.problem_statement_path = self.add_folder(self.out_dir, 'problem_statement')
        self.data_path = self.add_folder(self.out_dir, 'data')
        self.sample_data_path = self.add_folder(self.data_path, 'sample')
        self.secret_data_path = self.add_folder(self.data_path, 'secret')

        self.generator_names: set[str] = set()
        
        self.check_type = ''
        
    def force_mkdir(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        return path
        
    def add_folder(self, path: Path, *subfolders) -> Path:
        for subfolder in subfolders:
            path = self.force_mkdir(path / subfolder)
        return path
        
    def log(self, *args):
        if self.verbose:
            print(*args)
        
    def extract_package_member_to(self, member: str, dest: Path):
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

        if self.test_generation_info:
            files_to_exclude = set([
                'files/olymp.sty',
                'files/problem.tex',
                'files/statements.ftl',
            ])
            for resource_tags in self.problem_data.findall('./files/resources/file'):
                file_path = resource_tags.get('path', '')
                if file_path in files_to_exclude:
                    continue
                self.extract_package_member_to(file_path, self.secret_data_path / Path(file_path).name)

            for executable_tags in self.problem_data.findall('./files/executables/executable/source'):
                file_path = executable_tags.get('path', '')
                if any(generator_name in file_path for generator_name in self.generator_names):
                    self.extract_package_member_to(file_path, self.secret_data_path / Path(file_path).name)

    def process_testset(self, testset: ET.Element):
        testset_name = testset.get('name', '')
        self.log('Processing testset', testset_name)
        
        cur_sample_data_path = self.sample_data_path
        cur_secret_data_path = self.add_folder(self.secret_data_path, testset_name)

        input_path_pattern_tag = testset.find('input-path-pattern')
        answer_path_pattern_tag = testset.find('answer-path-pattern')
        testcount_tag = testset.find('test-count')
        if (input_path_pattern_tag is None or
            answer_path_pattern_tag is None or
            testcount_tag is None):
            self.log(f'Skip processing testset {testset_name}. Tags not found.')
            return  
        
        input_path_pattern = input_path_pattern_tag.text or ''
        answer_path_pattern = answer_path_pattern_tag.text or ''
        testcount = int(testcount_tag.text or '0')
        test_tags = testset.findall('./tests/test')

        generation_scripts: list[str] = []
        
        for test_id in range(1, testcount + 1):
            input_filename = input_path_pattern % test_id
            answer_filename = answer_path_pattern % test_id
            test_tag = test_tags[test_id - 1]
            is_sample = test_tag.get('sample') == 'true'
            
            dest_path = cur_sample_data_path if is_sample else cur_secret_data_path
            input_file_name = f'{test_id}.in'
            output_file_name = f'{test_id}.ans'
            self.extract_package_member_to(input_filename, dest_path / input_file_name)
            self.extract_package_member_to(answer_filename, dest_path / output_file_name)
            
            test_generation_script = test_tag.get('cmd')
            if test_generation_script is not None:
                generation_scripts.append(f'{test_generation_script} > {input_file_name}')
                self.generator_names.add(test_generation_script.split()[0])
        if self.test_generation_info:
            path = cur_secret_data_path/ '_gen-test-script'
            disclaimer = textwrap.dedent("""
            # Actual tests were generated on Polygon.
            # This file is generated and not meant to be ran.
            # This file is here to demonstrate how the generators were used to generate the test.
            """)
            path.write_text(disclaimer + '\n' + '\n'.join(generation_scripts))
            self.log(f'Write f{path}')
            
    def process_solutions(self):
        self.log('Processing solutions')
        solution_tags = self.problem_data.findall('./assets/solutions/solution')
        submission_path = self.out_dir / 'submissions'
        for solution_tag in solution_tags:
            source_tag = solution_tag.find('source')
            tag = solution_tag.get('tag')
            if source_tag is None:
                continue
            path = source_tag.get('path', '')
            if tag in ['accepted', 'main']:
                sol_out_dir = self.add_folder(submission_path, 'accepted')
            elif tag == 'time-limit-exceeded':
                sol_out_dir = self.add_folder(submission_path, 'time_limit_exceeded')
            elif tag == 'wrong-answer':
                sol_out_dir = self.add_folder(submission_path, 'wrong_answer')
            else:
                self.log('Skip solution', path, f'of tag {tag}')
                continue
            self.extract_package_member_to(path, sol_out_dir / Path(path).name)
            
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
        if source_tag == None:
            return
        source_path = source_tag.get('path', '')
        checker_out_dir = self.add_folder(self.out_dir, 'output_validators', 'checker')
        self.extract_package_member_to(source_path, checker_out_dir / Path(source_path).name)
        if 'cpp' in source_tag.get('type', ''):
            shutil.copy(self.testlib_path, checker_out_dir)
    
    def _process_validator(self):
        validator_tags = self.problem_data.findall('./assets/validators/validator')
        if len(validator_tags) == 0:
            return
        validator_tag = validator_tags[0]
        source_tag = validator_tag.find('source')
        if source_tag is None:
            return
        source_path = source_tag.get('path', '')
        validator_out_dir = self.add_folder(self.out_dir, 'input_validators', 'extracted_validator')
        self.extract_package_member_to(source_path, validator_out_dir / Path(source_path).name)
        if 'cpp' in source_tag.get('type', ''):
            shutil.copy(self.testlib_path, validator_out_dir)
            
    def _process_interactor(self):
        # TODO
        pass
    
    def write_problem_yaml(self):
        with open(self.out_dir / 'problem.yaml', 'w') as f:
            print('source:', self.problem_data.get('url'), file=f)
            print('license:', self.license, file=f)
            print('limits:', file=f)
            print('  time_multiplier: 2', file=f)
            if 'custom' in self.checker_type:
                print('validation:', self.checker_type, file=f)
            elif 'std::' in self.checker_type:
                if self.checker_type == 'std::rcmp4.cpp':
                    print('validation:', file=f)
                    print('  validator_flags: float_tolerance 1e-4', file=f)
                if self.checker_type == 'std::rcmp6.cpp':
                    print('validation:', file=f)
                    print('  validator_flags: float_tolerance 1e-6', file=f)
                if self.checker_type == 'std::rcmp9.cpp':
                    print('validation:', file=f)
                    print('  validator_flags: float_tolerance 1e-9', file=f)

def main():
    args = build_argparser().parse_args()
    print(args)
    p2k = Polygon2Kattis(
            package_zip_file=args.package,
            out_dir=args.out_dir,
            lang=args.lang,
            verbose=args.verbose,
            license=args.license,
            test_generation_info=args.test_generation_info
            )
    p2k.process_statement()
    p2k.process_tests()
    p2k.process_solutions()
    p2k.process_checker_validator_interactor()
    if args.write_problem_yaml:
        p2k.write_problem_yaml()
    
    p2k.log('done')
            
main()
