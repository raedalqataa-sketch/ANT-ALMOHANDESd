"""Apply the minimal 404 correction without replacing unrelated project edits."""
import argparse
from pathlib import Path
OLD='/villa-engine/generate/?embedded=1'
NEW='/villa-engine/generate/index.html?embedded=1'

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('project',type=Path);args=parser.parse_args()
 files=[args.project/'src/components/villa-generator.tsx',args.project/'src/components/villa-generator.test.tsx']
 proposed=[]
 for path in files:
  source=path.read_text()
  if OLD not in source:
   if NEW in source:continue
   raise SystemExit('Unexpected source; review manually: '+str(path))
  if source.count(OLD)!=1:raise SystemExit('Ambiguous source; review manually: '+str(path))
  proposed.append((path,source.replace(OLD,NEW)))
 for path,source in proposed:path.write_text(source);print('Updated',path)
 if not proposed:print('The explicit HTML path is already present.')

if __name__=='__main__':main()
