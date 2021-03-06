#
# Buildbot scripts to create 'buildbot factories' for pocl and LLVM.
# Author: Kalle Raiskila, no rights reserved.
#

from buildbot.process import factory
from buildbot.steps import source
from buildbot.steps.shell import ShellCommand, Compile
from buildbot.status.results import *
import os

#The names of the external tests sources
AMD_test_pkg='AMD-APP-SDK-v2.8-RC-lnx64.tgz'
ViennaCL_test_pkg='ViennaCL-1.5.1-src.tar.gz'


def createPoclFactory(	environ={},
			repository='https://github.com/pocl/pocl.git',
			branch='master',
			buildICD=True,
			llvm_dir='/usr/',
			icd_dir='/usr/',
			tests_dir='',
			config_opts='',
			pedantic=True
			):
	"""
	Create a buildbot factory object that builds pocl.
	
	environ		Dictionary:   The environment variables to append to the build. PATH and
				LD_LIBRARY_PATH will be added from llvm_dir (if given).
	repository	String: the repo to build from. defaults to pocl on github
	branch		String: the branch in 'repository' to build from. default to master
	buildICD	Bool:	if false, the ICD extension is not built.
	llvm_dir	String: LLVM installation dir. I.e. without the 'bin/' or 'lib/'.
	icd_dir		String: ICD loader installation dir. We expect here to be a ICD loader that
				understand the OCL_ICD_VENDORS parameter, i.e. ocl-icd or patched
				Khronos loader.
	tests_dir	String: Path where the extenral testsuite packages can be copied from.
				('cp' is used, so they need to be on the same filesystem).
				NOTE: currently only a placeholder - not tested on the public buildbot
	config_opts	String: extra options to pass to ./configure
	"""

	environ['PATH'] = llvm_dir+"/bin/:${PATH}"
	environ['LD_LIBRARY_PATH'] = llvm_dir+"/lib/:${LD_LIBRARY_PATH}"



	f = factory.BuildFactory()
	f.addStep(source.Git(
			repourl=repository,
			#mode='update',
			#rm -rf the build tree. Have this only when changing
			#branches during releases
			mode='clobber',
			branch=branch ))


	f.addStep(ShellCommand(command=["./autogen.sh"],
				haltOnFailure=True,
				name="autoconfig",
				env=environ,
				description="autoconfiging",
				descriptionDone="autoconf"))

	f.addStep(ShellCommand(
		haltOnFailure=True,
		command=["cp", "-u", tests_dir+AMD_test_pkg, 
		         "examples/AMD/"+AMD_test_pkg],
		name="copy AMD",
		description="copying",
		descriptionDone="copied AMD",
		#kludge around 'cp' always complaining if source is missing
		decodeRC={0:SUCCESS,1:SUCCESS}
		))
	f.addStep(ShellCommand(
		haltOnFailure=False,
		command=["cp", "-u", tests_dir+ViennaCL_test_pkg,
		         "examples/ViennaCL/"+ViennaCL_test_pkg],
		name="copy ViennaCL",
		description="copying",
		descriptionDone="copied ViennaCL",
		decodeRC={0:SUCCESS,1:SUCCESS}
		))

	configOpts=config_opts.split(' ')
	if pedantic==True:
		configOpts = configOpts + ['--enable-pedantic']
	if buildICD==False:
		configOpts = configOpts + ['--disable-icd']

	f.addStep(ShellCommand(command=["./configure"] + configOpts,
				haltOnFailure=True,
				name="configure",
				env=environ,
				description="configureing",
				descriptionDone="configure"))
	f.addStep(Compile(env=environ ))
	
	#enable this later
	ttacheck=False
	if ttacheck:
		f.addStep(ShellCommand(command=["./tools/scripts/run_tta_tests"],
				haltOnFailure=True,
				name="checks",
				env=environ,
				description="testing",
				descriptionDone="tests",
				logfiles={"test.log": "tests/testsuite.log"},
				timeout=60*60))
	else:
		f.addStep(ShellCommand(command=["make", "check"],
				#for beagle, contiunu to clean it up
				#haltOnFailure=True,
				name="checks",
				env=environ,
				description="testing",
				descriptionDone="tests",
				logfiles={"test.log": "tests/testsuite.log"},
				#blas3 alone takes 15-20 min.
				timeout=60*60))
	


	#Keep this here for a reference, if we want to record the benchmarking progress at some point in time
	#Benchmark only the vanilla pocl
	#if do_benchmark and baseurl=='lp:' and defaultbranch=='pocl':
	#	f.addStep(
	#		ShellCommand(
	#			haltOnFailure=True,
	#			env=environ,
	#			command=['./tools/scripts/benchmark.py', '--lightweight', '-o', 'benchmark_log.txt' ],
	#			logfiles = {'log.txt': 'benchmark_log.txt'},
	#			name = 'benchmark',
	#			description='benchmarking',
	#			descriptionDone='benchmarked',
	#			# 4hour timeout - PPC runs for a *long* time
	#			timeout=60*60*4))
	#	f.addStep(
	#		ShellCommand(
	#			command=[
	#				'scp',
	#				'benchmark_log.txt',
	#				WithProperties("marvin:/var/www/pocl_benchmarks/benchmark-"+processor+"-r%(got_revision)s.txt")],
	#			name = 'copy benchmark',
	#			description='copying',
	#			descriptionDone='copied'))

	return f

#######
## LLVM/clang builder
##

def createLLVMFactory(srcdir, branch, builddir, installdir):
	f = factory.BuildFactory()
	f.addStep(
		SVN(
			name='svn-llvm',
			mode='update',
			baseURL='http://llvm.org/svn/llvm-project/llvm/',
			defaultBranch=branch,
			workdir=srcdir))
	f.addStep(
		SVN(
			name='svn-clang',
			mode='update',
			baseURL='http://llvm.org/svn/llvm-project/cfe/',
			defaultBranch=branch,
			workdir='%s/tools/clang' % srcdir))
	f.addStep(
		ShellCommand(
			command=[
				'%s/configure' % srcdir,
				'--prefix=' + installdir,
				'--enable-targets=host',
				'--enable-shared', '--disable-static'],
			workdir=builddir,
			haltOnFailure=True,
			name="configure",
			descriptionDone='configure',
			description='configuring'))
	f.addStep(
		ShellCommand(
			command=['make'],
			workdir=builddir,
			haltOnFailure=True,
			name = "compile",
			descriptionDone = 'compile',
			description='compiling'))
	f.addStep(
		ShellCommand(
			command=['make', 'check'],
			workdir=builddir,
			name='check',
			descriptionDone='check',
			haltOnFailure=True,
			description='checking'))
	f.addStep(
		ShellCommand(
			command=['make', 'install'],
			workdir=builddir,
			haltOnFailure=True,
			name = 'install',
			descriptionDone='install',
			description='installing'))

	return f

# vim: set noexpandtab:
