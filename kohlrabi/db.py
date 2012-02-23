import datetime
from sqlalchemy import *
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta

report_tables = set()

metadata = MetaData()
session = None

def bind(engine_path, import_module, create_tables=False):
    global session
    create_kw = {}
    if engine_path.startswith('mysql+mysqldb'):
        create_kw['pool_recycle'] = 3600
    engine = create_engine(engine_path, **create_kw)
    Session = sessionmaker(bind=engine)
    session = Session()

    if import_module:
        __import__(import_module)
        for v in report_tables:
            if v.__name__ not in globals().keys():
                globals()[v.__name__] = v

    if engine_path.endswith(':memory:') or create_tables:
        metadata.create_all(engine)

class _Base(object):

    @classmethod
    def current_date(cls):
        row = session.query(cls).order_by(cls.date.desc()).first()
        if row:
            return row.date
        else:
            return None

Base = declarative_base(metadata=metadata, cls=_Base)

class ReportMeta(DeclarativeMeta):

    def __init__(cls, name, bases, cls_dict):
        super(ReportMeta, cls).__init__(name, bases, cls_dict)
        report_tables.add(cls)

        def format_float(v):
            return '%1.2f' % (v or 0)

        def format_int(v):
            return '%d' % (v or 0)

        def format_str(s):
            return str(s)

        for r in cls.html_table:
            coltype = type(cls.__table__._columns[r.name].type)
            if coltype is Float:
                r.format = format_float if not r.format else r.format
                if not r.css_class:
                    r.css_class = 'number'
            elif coltype is Integer:
                r.format = format_int if not r.format else r.format
                if not r.css_class:
                    r.css_class = 'number'
            else:
                r.format = format_str if not r.format else r.format

    def load_report(cls, data, date=None):
        date = date or datetime.date.today()
        for row in session.query(cls).filter(cls.date == date):
            session.delete(row)
        for datum in data:
            if hasattr(cls, 'column_map'):
                datum = dict((cls.column_map[k], v) for k, v in datum.iteritems())
            datum['date'] = date

            # SQLAlchemy will throw an exception if we give it any extra
            # columns, so make sure the dataset it pruned to columns that
            # actually exist
            for k in datum.keys():
                # XXX: this is a really crude heuristic
                if not hasattr(cls, k):
                    del datum[k]

            session.add(cls(**datum))
        session.commit()

    def dates(cls, limit=None):
        ds = session.query(cls.date).group_by(cls.date).order_by(cls.date.desc())
        if limit is not None:
            return (row.date for row in ds[:limit])
        else:
            return (row.date for row in ds)

class ReportColumn(object):

    def __init__(self, display, name, css_class='', format=None):
        self.display = display
        self.name = name
        self.css_class = css_class
        self.format = format

def format_percentage(val):
    return '%1.2f%%' % (val * 100.0,)

def format_kb(val):
    return '%1.2f' % (val / 1024.0,)
