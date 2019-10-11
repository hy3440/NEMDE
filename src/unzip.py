import pathlib
import zipfile

current = pathlib.Path('.')
for p in current.glob('*.zip'):
    with zipfile.ZipFile(p) as zf:
        name = zf.namelist()[0]
        csvname = '_'.join(name.split('_')[:-1])
        with (current / '{}.csv'.format(csvname)).open('wb') as f:
            f.write(zf.read(name))
    p.unlink()
