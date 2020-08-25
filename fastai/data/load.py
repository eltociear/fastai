# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/02_data.load.ipynb (unless otherwise specified).

__all__ = ['fa_collate', 'fa_convert', 'SkipItemException', 'DataLoader']

# Cell
from ..torch_basics import *

from torch.utils.data.dataloader import _MultiProcessingDataLoaderIter,_SingleProcessDataLoaderIter,_DatasetKind

# Cell
_loaders = (_MultiProcessingDataLoaderIter,_SingleProcessDataLoaderIter)

# Cell
def _wif(worker_id):
    set_num_threads(1)
    info = get_worker_info()
    ds = info.dataset.d
    ds.nw,ds.offs = info.num_workers,info.id
    set_seed(info.seed)
    ds.wif()

class _FakeLoader:
    _IterableDataset_len_called,_auto_collation,collate_fn,drop_last,dataset_kind,_dataset_kind,_index_sampler,generator,prefetch_factor = (
        None,False,noops,False,_DatasetKind.Iterable,_DatasetKind.Iterable,Inf.count,None,2)
    def __init__(self, d, pin_memory, num_workers, timeout):
        self.dataset,self.default,self.worker_init_fn = self,d,_wif
        store_attr(self, 'd,pin_memory,num_workers,timeout')

    def __iter__(self): return iter(self.d.create_batches(self.d.sample()))

    @property
    def multiprocessing_context(self): return (None,multiprocessing)[self.num_workers>0]

    @contextmanager
    def no_multiproc(self):
        old_nw = self.num_workers
        try:
            self.num_workers = 0
            yield self.d
        finally: self.num_workers = old_nw

_collate_types = (ndarray, Tensor, typing.Mapping, str)

# Cell
def fa_collate(t):
    "A replacement for PyTorch `default_collate` which maintains types and handles `Sequence`s"
    b = t[0]
    return (default_collate(t) if isinstance(b, _collate_types)
            else type(t[0])([fa_collate(s) for s in zip(*t)]) if isinstance(b, Sequence)
            else default_collate(t))

# Cell
def fa_convert(t):
    "A replacement for PyTorch `default_convert` which maintains types and handles `Sequence`s"
    return (default_convert(t) if isinstance(t, _collate_types)
            else type(t)([fa_convert(s) for s in t]) if isinstance(t, Sequence)
            else default_convert(t))

# Cell
class SkipItemException(Exception):
    "Raised to notify `DataLoader` to skip an item"
    pass

# Cell
@log_args(but='dataset,wif,create_batch,create_batches,create_item,retain,get_idxs,sample,shuffle_fn,do_batch')
@funcs_kwargs
class DataLoader(GetAttr):
    _noop_methods = 'wif before_iter after_item before_batch after_batch after_iter'.split()
    for o in _noop_methods: exec(f"def {o}(self, x=None, *args, **kwargs): return x")
    _methods = _noop_methods + 'create_batches create_item create_batch retain \
        get_idxs sample shuffle_fn do_batch create_batch'.split()
    _default = 'dataset'
    def __init__(self, dataset=None, bs=None, num_workers=0, pin_memory=False, timeout=0, batch_size=None,
                 shuffle=False, drop_last=False, indexed=None, n=None, device=None, **kwargs):
        if batch_size is not None: bs = batch_size # PyTorch compatibility
        assert not (bs is None and drop_last)
        if indexed is None: indexed = dataset is not None and hasattr(dataset,'__getitem__')
        if n is None:
            try: n = len(dataset)
            except TypeError: pass
        store_attr(self, 'dataset,bs,shuffle,drop_last,indexed,n,pin_memory,timeout,device')
        self.rng,self.nw,self.offs = random.Random(random.randint(0,2**32-1)),1,0
        self.fake_l = _FakeLoader(self, pin_memory, num_workers, timeout)

    def __len__(self):
        if self.n is None: raise TypeError
        if self.bs is None: return self.n
        return self.n//self.bs + (0 if self.drop_last or self.n%self.bs==0 else 1)

    def get_idxs(self):
        idxs = Inf.count if self.indexed else Inf.nones
        if self.n is not None: idxs = list(itertools.islice(idxs, self.n))
        if self.shuffle: idxs = self.shuffle_fn(idxs)
        return idxs

    def sample(self):
        idxs = self.get_idxs()
        return (b for i,b in enumerate(idxs) if i//(self.bs or 1)%self.nw==self.offs)

    def __iter__(self):
        self.randomize()
        self.before_iter()
        for b in _loaders[self.fake_l.num_workers==0](self.fake_l):
            if self.device is not None: b = to_device(b, self.device)
            yield self.after_batch(b)
        self.after_iter()
        if hasattr(self, 'it'): delattr(self, 'it')

    def create_batches(self, samps):
        self.it = iter(self.dataset) if self.dataset is not None else None
        res = filter(lambda o:o is not None, map(self.do_item, samps))
        yield from map(self.do_batch, self.chunkify(res))

    def new(self, dataset=None, cls=None, **kwargs):
        if dataset is None: dataset = self.dataset
        if cls is None: cls = type(self)
        cur_kwargs = dict(dataset=dataset, num_workers=self.fake_l.num_workers, pin_memory=self.pin_memory, timeout=self.timeout,
                          bs=self.bs, shuffle=self.shuffle, drop_last=self.drop_last, indexed=self.indexed, device=self.device)
        for n in self._methods: cur_kwargs[n] = getattr(self, n)
        return cls(**merge(cur_kwargs, kwargs))

    @property
    def prebatched(self): return self.bs is None
    def do_item(self, s):
        try: return self.after_item(self.create_item(s))
        except SkipItemException: return None
    def chunkify(self, b): return b if self.prebatched else chunked(b, self.bs, self.drop_last)
    def shuffle_fn(self, idxs): return self.rng.sample(idxs, len(idxs))
    def randomize(self): self.rng = random.Random(self.rng.randint(0,2**32-1))
    def retain(self, res, b):  return retain_types(res, b[0] if is_listy(b) else b)
    def create_item(self, s):  return next(self.it) if s is None else self.dataset[s]
    def create_batch(self, b): return (fa_collate,fa_convert)[self.prebatched](b)
    def do_batch(self, b): return self.retain(self.create_batch(self.before_batch(b)), b)
    def to(self, device): self.device = device
    def one_batch(self):
        if self.n is not None and len(self)==0: raise ValueError(f'This DataLoader does not contain any batches')
        with self.fake_l.no_multiproc(): res = first(self)
        if hasattr(self, 'it'): delattr(self, 'it')
        return res

# Cell
add_docs(DataLoader, "API compatible with PyTorch DataLoader, with a lot more callbacks and flexibility",
         get_idxs = "TODO",
         sample = "TODO",
         create_batches = "TODO",
         new = "TODO",
         prebatched = "TODO",
         do_item = "TODO",
         chunkify = "TODO",
         shuffle_fn = "TODO",
         randomize = "TODO",
         retain = "TODO",
         create_item = "TODO",
         create_batch = "TODO",
         do_batch = "TODO",
         to = "TODO",
         one_batch = "TODO",
         wif  = "TODO",
         before_iter = "TODO",
         after_item = "TODO",
         before_batch = "TODO",
         after_batch = "TODO",
         after_iter  = "TODO")