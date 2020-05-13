from mOTUlizer.classes.MetaBin import MetaBin
from mOTUlizer.classes.COGs import *
import subprocess
import tempfile
import os
from mOTUlizer.config import *
from random import shuffle, choice
from math import log10
import sys
import json
from tqdm import tqdm

mean = lambda x : sum(x)/len(x)

class mOTU:
    def __len__(self):
        return len(self.members)

    def __repr__(self):
        return "< {tax} mOTU {name}, of {len} members >".format(name = self.name, len = len(self), tax =  None ) #self.consensus_tax()[0].split(";")[-1])

    def __init__(self, **kwargs):
        if "cog_dict" in kwargs:
            self.__for_mOTUpan(**kwargs)

        if "bins" in kwargs:
            self.__from_bins(**kwargs)


    def __for_mOTUpan(self, name, faas, cog_dict, checkm_dict):
        self.name = name
        self.faas = faas
        if  not cog_dict :
            tt = compute_COGs(self.faas, name = name + "COG")
            self.cog_dict = tt['genome2cogs']
            self.aa2cog = tt['aa2cog']
        else :
            self.cog_dict = cog_dict
            self.aa2cog = {}

        if checkm_dict == "length_seed" :
            max_len = max([len(cogs) for cogs in self.cog_dict.values()])
            checkm_dict = {}
            for f in self.cog_dict:
                checkm_dict[f] = 100*len(self.cog_dict[f])/max_len
        self.members = [MetaBin(bin_name, self.cog_dict[bin_name], self.faas.get(bin_name), None, checkm_dict.get(bin_name)) for bin_name in self.cog_dict.keys()]
        self.core = None

        self.cogCounts = {c : 0 for c in set.union(*[mag.cogs for mag in self.members])}
        for mag in self.members:
            for cog in mag.cogs:
                    self.cogCounts[cog] += 1

        self.likelies = self.__core_likelyhood()

    def __getitem__(self, i):
        return self.members[i]

    def avg_cog_content(self):
        return sum([len(m.cogs) for m in self.members])/len(self)

    def consensus_tax(self):
        taxos = [bin.taxonomy for bin in self.members]
        temp = {}
        for i in range(0,7):
            leveled = [t[i] for t in taxos]
            counts = {l : leveled.count(l) for l in set(leveled)}
            win = max(counts.items(), key = lambda x : x[1])
            temp[i] = win
        output = ["", []]
        for i in range(7):
            if temp[i][0] == "":
                break
            output[0] += ";" + temp[i][0]
            output[1] += [temp[i][1] / len(self)]
        output[0] = output[0][1:]
        return tuple(output)

    def overlap_matrix(self):
        if not hasattr(self, 'overlap_dict'):
            self.overlap_dict = {(i,j) : len(i.overlap(j))/len(i.cogs) for i in self.members for j in self.members if i != j}
        return self.overlap_dict

    def mean_overlap(self) :
        return mean(list(self.overlap_matrix().values()))

    def fastani_matrix(self):
        if not hasattr(self, 'fastani_dict'):
            cmd = "fastANI --ql {temp_file}  --rl {temp_file}  -o {temp_out} -t {threads} 2> /dev/null"
            temp_inp = tempfile.NamedTemporaryFile()
            temp_out = tempfile.NamedTemporaryFile()

            with open(temp_inp.name, "w") as handle:
                handle.writelines([t.genome + "\n" for t in self.members ])

            cmd = cmd.format(temp_file = temp_inp.name, temp_out = temp_out.name, threads = THREADS)

            subprocess.call(cmd, shell=True)

            with open(temp_out.name ) as handle:
                self.fastani_dict = {}
                for l in handle:
                    q = os.path.basename(l.split()[0][:-4])
                    s = os.path.basename(l.split()[1][:-4])
                    if q  != s:
                        value = float(l.split()[2])
                        self.fastani_dict[(q,s)] = value
        return self.fastani_dict


    def get_stats(self):
        out = {}
        out[self.name] = { "nb_genomes" : len(self),
        "core" : list(self.core) if self.core else None,
        "aux_genome" : [k for k,v in self.cogCounts.items() if k not in self.core] if self.core else None ,
        "singleton_cogs" : [k for k,v in self.cogCounts.items() if k not in self.core if v == 1] if self.core else None,
        "cogs" : {'genome' : {k : list(v) for k,v in self.cog_dict.items()}, 'aa' : self.aa2cog} if self.aa2cog else None,
        "mean_ANI" : self.get_mean_ani() if (self.fastani_dict or all([hasattr(g, "genome") for g in self])) else None,
        "genomes" : [v.get_data() for v in self]
        }
        return out

    def get_mean_ani(self):
        dist_dict = self.fastani_matrix()
        dists = [dist_dict.get((a.name,b.name)) for a in self for b in self if a != b ]
        missing_edges = sum([d is None for d in dists])
        found_edges = [d is None for d in dists]
        
        return {'mean_ANI' : sum([d for d in dists if d])/len(found_edges) if len(found_edges) > 0 else None, 'missing_edges' : missing_edges, 'total_edges' : len(found_edges) + missing_edges}

    def __core_likelyhood(self, max_it = 20):
        likelies = {cog : self.__core_likely(cog) for cog in self.cogCounts}
        self.core = set([c for c, v in likelies.items() if v > 0])
        core_len = len(self.core)
        i = 1
        print("iteration 1 : ", core_len, "LHR:" , sum(likelies.values()), file = sys.stderr)
        for mag in self:
            if len(self.core) > 0:
                mag.new_completness = 100*len(mag.cogs.intersection(self.core))/len(self.core)
            else :
                mag.new_completness = 0
            mag.new_completness = mag.new_completness if mag.new_completness < 99.9 else 99.9
            mag.new_completness = mag.new_completness if mag.new_completness > 0 else 0.1
        for i in range(2,max_it):
            likelies = {cog : self.__core_likely(cog, complet = "new", core_size = core_len) for cog in self.cogCounts}
            self.core = set([c for c, v in likelies.items() if v > 0])
            new_core_len = len(self.core)
            for mag in self:
                if len(self.core) > 0:
                    mag.new_completness = 100*len(mag.cogs.intersection(self.core))/len(self.core)
                else :
                    mag.new_completness = 0
                mag.new_completness = mag.new_completness if mag.new_completness < 99.9 else 99.9
                mag.new_completness = mag.new_completness if mag.new_completness > 0 else 0.01

            print("iteration",i, ": ", new_core_len, "LHR:" , sum(likelies.values()), file = sys.stderr)
            if new_core_len == core_len:
               break
            else :
                core_len =new_core_len

        json.dump({ self.name : {"nb_mags" : len(self), "core_len" : core_len, "mean_starting_completeness" :  mean([b.checkm_complet for b in self]), "mean_new_completness" : mean([b.new_completness for b in self]), "LHR"  :  sum([l if l > 0 else -l for l in likelies.values()]), "mean_est_binsize" : mean([100*len(b.cogs)/b.new_completness for b in self])}}, sys.stderr )
        print(file = sys.stderr)
        self.iterations = i -1
        return likelies

    def __core_prob(self, cog, complet = "checkm"):
        comp = lambda mag : (mag.checkm_complet if complet =="checkm" else mag.new_completness)/100
        presence = [log10(comp(mag)) for mag in self if cog in mag.cogs]
        abscence = [log10(1 - comp(mag)) for mag in self if cog not in mag.cogs]
        return sum(presence + abscence)

    def __pange_prob(self, cog, core_size, complet = "checkm"):
        pool_size = sum(self.cogCounts.values())
        comp = lambda mag : (mag.checkm_complet if complet =="checkm" else mag.new_completness)/100
        #presence = [1 - (1-self.cogCounts[cog]/pool_size)**(len(mag.cogs)-(core_size*comp(mag))) for mag in self if cog in mag.cogs]
        #abscence = [ (1-self.cogCounts[cog]/pool_size)**(len(mag.cogs)-(core_size*comp(mag))) for mag in self if cog not in mag.cogs]

#        presence = [ log10(1 -   ( 1 - 1/len(self.cogCounts))**(len(mag.cogs)-(core_size*comp(mag)))) for mag in self if cog in mag.cogs]
#        abscence = [       log10(( 1 - 1/len(self.cogCounts))**(len(mag.cogs)-(core_size*comp(mag)))) for mag in self if cog not in mag.cogs]
        mag_prob = {mag : ( 1-self.cogCounts[cog]/pool_size )**(len(mag.cogs)-(core_size*comp(mag))) for mag in self}

        presence = [ log10(1 -   mag_prob[mag]) if mag_prob[mag] < 1 else MIN_PROB                for mag in self if cog in mag.cogs]
        abscence = [ log10(      mag_prob[mag]) if mag_prob[mag] > 0 else log10(1-(10**MIN_PROB)) for mag in self if cog not in mag.cogs]

        #abscence = [ 1-self.cogCounts[cog]/len(self)*comp(mag) for mag in self if cog not in mag.cogs]
        #presence = [ self.cogCounts[cog]/len(self)*comp(mag) for mag in self if cog not in mag.cogs]

        return sum(presence + abscence)

    def __core_likely(self, cog, complet = "checkm", core_size = 0):
        pange_prob = self.__pange_prob(cog, core_size, complet)
        return self.__core_prob(cog, complet) - pange_prob

    def nb_cogs(self):
        return mean([b.estimate_nb_cogs() for b in self if b.new_completness > 40 ])

    def get_pangenome_size(self, singletons = False):
        return len([k for k,v in self.cogCounts.items() if k not in self.core and v > (0 if singletons else 1)])


    def rarefy_pangenome(self, reps = 100, singletons = False, custom_cogs = None):
        def __min_95(ll):
            ll.sort_values()
            return list(ll.sort_values())[round(len(ll)*0.05)]

        def __max_95(ll):
            ll.sort_values()
            return list(ll.sort_values())[round(len(ll)*0.95)]

        def __genome_count(ll):
            return ll[0]

        __genome_count.__name__ = "genome_count"
        __max_95.__name__ = "max_95"
        __min_95.__name__ = "min_95"

        pange = set.union(*custom_cogs) if custom_cogs else {k for k,v in self.cogCounts.items() if k not in self.core and v > (0 if singletons else 1)}
        series = []
        for i in range(reps):
            series += [{ 'rep' : i , 'genome_count' : 0, 'pangenome_size' : 0}]
            m = custom_cogs if custom_cogs else [m.cogs for m in self.members.copy()]
            shuffle(m)
            founds = set()
            for j,mm in enumerate(m):
                founds = founds.union(mm.intersection(pange))
                series += [{ 'rep' : i , 'genome_count' : j+1, 'pangenome_size' : len(founds)}]

        t_pandas = pandas.DataFrame.from_records(series)[['genome_count', 'pangenome_size']]
        t_pandas = t_pandas.groupby('genome_count').agg({'genome_count' : [__genome_count] ,'pangenome_size' : [mean, std, __min_95, __max_95]} )
        t_pandas.columns = ["rr_" + p[1] for p in t_pandas.columns]
        t_pandas = t_pandas.to_dict(orient="index")
        tt = self.get_otu_stats()
        for v in t_pandas.values():
            v.update(tt)
        return t_pandas



    def __from_bins(self, bins, name,dist_dict = None ):
        self.name = name

        self.members = bins
        self.core = None
        self.fastani_dict = dist_dict
        self.aa2cog = None


    @classmethod
    def cluster_MetaBins(cls , all_bins, dist_dict, ani_cutoff = 95, prefix = "mOTU_", mag_complete = 40, mag_contamin = 5, sub_complete = 0, sub_contamin = 100):
        import igraph

        print("seeding bin-graph")

        all_bins = {a.name : a for a in all_bins}

        tt = [(k, v.checkm_complet, v.checkm_contamin) for k, v in all_bins.items() if v.checkm_complet > 0]

        good_mag = lambda b : all_bins[b].checkm_complet > mag_complete and all_bins[b].checkm_contamin < mag_contamin
        decent_sub = lambda b : all_bins[b].checkm_complet > sub_complete and all_bins[b].checkm_contamin < mag_contamin and not good_mag(b)
        good_pairs = [k for k,v  in tqdm(dist_dict.items()) if v > ani_cutoff and dist_dict.get((k[1],k[0]), 0) > ani_cutoff and good_mag(k[0]) and good_mag(k[1])]
        species_graph = igraph.Graph()
        vertexDeict = { v : i for i,v in enumerate(set([x for k in good_pairs for x in k]))}
        rev_vertexDeict = { v : i for i,v in vertexDeict.items()}
        species_graph.add_vertices(len(vertexDeict))
        species_graph.add_edges([(vertexDeict[k[0]], vertexDeict[k[1]]) for k in good_pairs])

        print("getting clusters")

        genome_clusters = [[rev_vertexDeict[cc] for cc in c ] for c in species_graph.components(mode=igraph.STRONG)]

        mean = lambda l : sum([len(ll) for ll in l])/len(l)

        print("recruiting to graph of the", len(genome_clusters) ," mOTUs of mean length", mean(genome_clusters))


        left_pairs = {k : v for k, v in tqdm(dist_dict.items()) if v > ani_cutoff and k[0] != k[1] and ((decent_sub(k[0]) and good_mag(k[1])) or (decent_sub(k[1]) and good_mag(k[0])))}
        print("looking for good_left pairs")
        subs = {l[0] : (None,0) for l in left_pairs}

        print("looking for best mOTU match")
        for p,ani in tqdm(left_pairs.items()):
            if subs[p[0]][1] < ani:
                subs[p[0]] = (p[1], ani)

        genome_clusters = [set(gg) for gg in genome_clusters]

        print("append to the", len(genome_clusters) ,"mOTUs of mean length", mean(genome_clusters))
        for k, v in tqdm(subs.items()):
            for g in genome_clusters:
                if v[0] in g :
                    g.add(k)

        genome_clusters = [list(gg) for gg in genome_clusters]

        print("processing the", len(genome_clusters) ,"mOTUs of mean length", mean(genome_clusters))
        #print(genome_clusters)

        zeros = len(str(len(genome_clusters)))
        motus = [ mOTU(bins = [all_bins[gg] for gg in gs], name = prefix + str(i).zfill(zeros), dist_dict = {(k,l) : dist_dict[(k,l)] for k in gs for l in gs if (k,l) in dist_dict}) for i, gs in tqdm(enumerate(genome_clusters))]


        return motus
