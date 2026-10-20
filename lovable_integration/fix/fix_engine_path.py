"""Fix the explicit engine path and required iframe form permission."""
import argparse
from pathlib import Path
OLD='/villa-engine/generate/?embedded=1'
NEW='/villa-engine/generate/index.html?embedded=1'

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('project',type=Path);args=parser.parse_args()
 files=[args.project/'src/components/villa-generator.tsx',args.project/'src/components/villa-generator.test.tsx']
 proposed=[]
 for path in files:
  original=source=path.read_text()
  if OLD in source:
   if source.count(OLD)!=1:raise SystemExit('Ambiguous source; review manually: '+str(path))
   source=source.replace(OLD,NEW)
  elif NEW not in source:raise SystemExit('Unexpected source; review manually: '+str(path))
  if path.name=='villa-generator.tsx':
   old='sandbox="allow-scripts allow-same-origin allow-downloads"'
   new='sandbox="allow-scripts allow-same-origin allow-forms allow-downloads allow-popups"'
   if old in source:source=source.replace(old,new)
   elif new not in source:raise SystemExit('Unexpected iframe permissions; review manually: '+str(path))
  if source!=original:proposed.append((path,source))
 for path,source in proposed:path.write_text(source);print('Updated',path)
 if not proposed:print('The engine path and iframe permissions are already corrected.')

if __name__=='__main__':main()
