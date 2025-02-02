# mOTUlizer

Utility to analyse a group of closely related MAGs/Genomes/bins/SUBs of more or less dubious origin. Right now it is composed of a number of programs:

* `mOTUlize.py` takes a set of genomes (I will use the term genome as a short hand for set of nucleotide sequences that presumably come from the same organism/population, can be incomplete, redundant or contaminated) and cluster them in to metagenomic Operational Taxonomic Units (mOTUs). Using similarity scores (by default ANI as computed by fastANI, but user can provide other similarities) a network is built based on (user defined) better quality genomes (for historical reasons called MAGs) by thresholding the similarities at a specific value (95% by default). The connected components of this graph are the mOTUs. Additionally lower quality genomes (SUBs, ) are recruited to the mOTU of whichever MAG they are most similar too if the similarity is above the threshold.

* `mOTUpan.py` computes the likelihood of gene-encoded traits to be expected in all of a set of genomes, e.g. of a trait to be in the core genome of a set of genomes (of possibly varying quality). Basically you provide to `mOTUpan` the set of proteomes of your genomes of interest (for example from the same mOTU or Genus) as well as a completeness prior of these genomes (for example [`checkm`](https://ecogenomics.github.io/CheckM/) output or a fixed value) and it computes gene clusters using [`mmseqs2`](https://github.com/soedinglab/MMseqs2), you can also provide your own genome encoded traits either as a `JSON`-file, or `TAB`-separated file (see example files). For each of these gene-clusters it will then compute the likelihood of it being in the core vs the likelihood of it not being, the ratio of these likelihoods will determine if a trait is considered core or not. This new partitioning can be used to update our completeness prior, and recomputed iteratively until convergence.

* `mOTUconvert.py` converts the output of diverse programs into input files for `mOTUpan.py`, currently includes methods for [`mmseqs2`](https://github.com/soedinglab/MMseqs2), [`roary`](https://sanger-pathogens.github.io/Roary/), [`PPanGGOLiN`](https://github.com/labgem/PPanGGOLiN), [`eggNOGmapper`](https://github.com/eggnogdb/eggnog-mapper), [`anvio`][https://merenlab.org/software/anvio/] pangenome databases.

* **experimental** `anvi-run-motupan.py` a anvi'o compatible version of `mOTUpan.py` a bit less options right now, but runs directly on anvi'o pangenome database

a number of example files are to be found in the `example_files`-folder, the `fasta`- and `gff`-files are the ones used for all the other files, these are generated by the always fantastic [`prokka`](example_files/fnas/). Also there is some reading material in the `mOTUlizer/doc` (a poster, a presentation and a very early paper draft, but at least it has the maths in it), the paper will eventually be available there!

## INSTALL

With conda:

```
conda install -c bioconda  motulizer
```

With pip:

```
pip install mOTUlizer
```

manually:

```
git clone https://github.com/moritzbuck/mOTUlizer.git
cd mOTUlizer
python setup.py install
```


## USAGE

### mOTUlize

To make OTUs and get some stats, needs [`fastANI`](https://github.com/ParBLiSS/FastANI) in the `PATH` if you do not provide a file for `--similarities`. To bypass fastANIs memory greedy nature, it runs it in blocks if needed.

simply run with:
```
mOTUlize.py --fnas example_files/fnas/*.fna -o output.tsv
```

Loads of little options if you do : `mOTUlize.py -h`

#### Key options:

* `--checkm`: provide a file containing completenesses and contaminations, see `mOTUpan`-section for detail, this time though, contamination is used... also, if not provided all genomes are assumed 'MAGs' e.g. high quality.

* `--similarities`: provide a file that contains pairwise similarities of genomes. The parser will ignore any lines containting the work query (yeah I know, dodgy, but that is it for now, it's based on the output of fastANI), and need at least three columns separated by `TAB`s. The first two columns are the two genome names, the third a similarity value between 0 and 100. As of now, the similarities are assumed to be asymetrical, only pairs where both pass the similarity threshold a kept for the network.
* `--keep-simi-file` : saves the similarity file generated by `fastANI`, can be used directly with `--similarities`. Good to use if you have a lot of genomes as the `fastANI` part is the slowest part, you can then use the same file with different cutoffs to tailor your clustering.
* `--MAG-completeness`/`--MAG-contamination`: controls which genomes are considered high quality, used for creating the mOTU-network
* `--SUB-completeness`/`--SUB-completeness`: controls which genomes are satelite unclassified bins (SUBs), lower quality bins that could be recruted to the MAGs (e.g. satelite around mOTUs, ok, not sure the acronym is really good, fine)
* `--similarity-cutoff`: similarity cutoff used to generate the mOTU network. By default 95, as in 95% ANI cutoff which has been recorded as a weirdly universal cutoff that separates species. This number is reported at a number of places [I will cite them soon, I promise, I will fill this with citations], and freaks me out. I thought it was an artefact, but if the completeness threshold is high enough, it is weirdly universal, found very very few exceptions... anyhow, you can change it.

### mOTUpan

An intro video [here](https://www.youtube.com/watch?v=VIeV1Gg5NS4):

[![mOTUpan for beginners](https://img.youtube.com/vi/VIeV1Gg5NS4/0.jpg)](https://www.youtube.com/watch?v=VIeV1Gg5NS4)


```
mOTUpan.py -h
```

Simplest command to run (needs mmseqs2 installed), but many options:

```
mOTUpan.py --faas *.faa -o output.tsv
```

#### Key options:

Check all flags in with `--help`, but here are some keys ones a bit more explained

* `--boots BOOTS` : runs `BOOTS` bootstraps, where artificial genomes are generated using the gene-partitioning obtained with `mOTUpan` (e.g. the core genes are in all artificial genomes, the others are a gene-pool with their frequency conserved), these genomes are then rarefied according to the posterioir completeness estimates. The bootstrap will provide an estimate of the false positive rate (e.g. fraction of core genes that might not be), the recall (fraction of core genes that have been classified as such in the bootstrap), and 'lowest false', the lowest frequency of any false positive found (e.g. should be high, meaning that your possible false positive are actually highly prevalent in your genome-set). Higher number of bootstraps give you a standard deviation for these numbers.

* `--cog_file` : can be used as an alternative to `--faas`, you can use it to provide you own gene-clusters (or other genetically encoded traits). The file should either be a `JSON`-file encoding a dictionary where the keys are the genome names and the values are lists of traits/genes (example in `example_files/example_genome2cog.json`). Or a `TAB`-separated file, where the first column is the genome name and followed by `TAB`-separated trait/gene-names (example in `example_files/example_genome2cog.tsv`).

* `--genome2cog_only` : only runs the gene-clustering (`mmseqs east_cluster`), returns a `JSON`-datastructure compatible with `--cog_file`

* `--checkm` : provide a file with Completenesses and Contaminations (Redundancy), it accepts the output of `checkm` or any other `TAB`-separated file with at least three columns: `Bin Id`, `Completeness`, and `Contamination`. `Bin Id` should be the genome names (e.g. file name minus extension), `Completeness` and `Contamination` values between 0 and 100. Note that `Contamination` is not actually used yet... A normal `check` output file is available at `example_files/example_checkm.txt` and a more generic completeness file that also works at `example_files/example_generic_completeness.tsv`.

* `--max_iter` : maximum number of iterations for the recursive aspect of motupan. You might want to put that to `1` if you have only few traits that would not be sufficient to estimate completeness.

### anvi-run-motupan

You need an anvi'o pangenome-database, and if you have it the genome-storage (for completenesses), great otherwise simply:

```
# if you want just a tsv :

anvi-run-motupan.py -p MYPANGENOME-PAN.db -g MYGENOMES.db -o MY_OUTPUT.tsv

# if you want to update the db, so it show up in anvi-display-pan

anvi-run-motupan.py -p MYPANGENOME-PAN.db -g MYGENOMES.db --store-in-db

```

### mOTUconvert

A small program generating appropriate input files for `mOTUpan.py` from the output of some of my favorite, or the public's favorite programs. It assumes the IDs in your protein `fasta`-file to be  `${genome_name}_[0-9]*` so genome-name separated from a number by an underscore. The gene name could have an underscore in it... But it might be risky, I did not code this very cleanly...

Runs as :

```
# check possible input file-types within

mOTUconvert.py --list

# running it
mOTUconvert.py  --in_type INFILE_TYPE INFILE > OUTPUT
# or
mOTUconvert.py  --in_type INFILE_TYPE -o OUTPUT INFILE

# you can then run mOTUpan as

mOTUpan.py --cog_file OUTPUT
```

In the `example_files`-folder a number of example input and output file are available.

## Citing and additional doc

Preprint for mOTUpan available on [bioRxiv](https://www.biorxiv.org/content/10.1101/2021.06.25.449606v1.full):

>mOTUpan: a robust Bayesian approach to leverage metagenome assembled genomes for core-genome estimation
>Moritz Buck, Maliheh Mehrshad, and Stefan Bertilsson
>bioRxiv 2021.06.25.449606; doi: https://doi.org/10.1101/2021.06.25.449606

A draft of a `release note` for mOTUlize is in the doc-folder, as well as the source of the previously mentioned mOTUpan paper and some slides
