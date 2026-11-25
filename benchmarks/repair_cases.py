"""Trusted, checked-in candidate patches; model can only select an identifier."""
import inspect
import random
import textwrap


def clamp_a(x):
    return min(10,max(0,x))


def clamp_b(x):
    return max(10,min(0,x))


def clamp_c(x):
    return min(10,x)


def unique_a(xs):
    return sorted(set(xs))


def unique_b(xs):
    return list(dict.fromkeys(xs))


def unique_c(xs):
    return list(xs)


def sum_a(xs):
    return sum(x for x in xs if x>0)


def sum_b(xs):
    return sum(xs)


def sum_c(xs):
    return sum(abs(x) for x in xs)


def average_a(xs):
    return sum(xs)/len(xs) if xs else 0


def average_b(xs):
    return sum(xs)/len(xs)


def average_c(xs):
    return sum(xs)//len(xs) if xs else 0


def group_a(xs):
    counts={}
    for x in xs:
        counts[x]=1
    return counts


def group_b(xs):
    counts={}
    for x in xs:
        counts[x]=counts.get(x,0)+1
    return counts


def group_c(xs):
    return {x:xs.count(x)-1 for x in xs}


def intervals_a(xs):
    return sorted(xs)


def intervals_b(xs):
    out=[]
    for start,end in sorted(xs):
        if out and start<=out[-1][1]:
            out[-1]=(out[-1][0],max(out[-1][1],end))
        else:
            out.append((start,end))
    return out


def intervals_c(xs):
    out=[]
    for start,end in sorted(xs):
        if out and start<out[-1][1]:
            out[-1]=(out[-1][0],end)
        else:
            out.append((start,end))
    return out


def path_a(xs):
    return "/".join(xs)


def path_b(xs):
    out=[]
    for x in xs:
        if x=="..":
            if not out:
                return None
            out.pop()
        elif x not in ("","."):
            out.append(x)
    return "/".join(out)


def path_c(xs):
    return "/".join(x for x in xs if x not in ("",".",".."))


def window_a(xs):
    best=0
    for i in range(len(xs)):
        seen=set()
        for x in xs[i:]:
            if x in seen: break
            seen.add(x)
            best=max(best,len(seen))
    return best


def window_b(xs):
    return len(set(xs))


def window_c(xs):
    return len(xs)


def topo_a(edges):
    return sorted(edges)


def topo_b(edges):
    left=set(edges)
    out=[]
    while left:
        ready=sorted(k for k in left if set(edges[k])<=set(out))
        if not ready:
            return None
        out.extend(ready)
        left.difference_update(ready)
    return out


def topo_c(edges):
    return list(edges)


SPECS=[
 ("simple","clamp","Clamp a number to the inclusive range 0 through 10.",(clamp_a,clamp_b,clamp_c),[(-3,0),(4,4),(13,10)]),
 ("simple","unique","Remove repeated values, preserving first occurrence order.",(unique_a,unique_b,unique_c),[([3,1,3,2],[3,1,2]),([],[]),([2,2],[2])]),
 ("simple","sum","Sum only strictly positive values.",(sum_a,sum_b,sum_c),[([2,-3,4],6),([-5],0),([],0)]),
 ("medium","average","Return arithmetic mean, or zero for empty input.",(average_a,average_b,average_c),[([1,2],1.5),([],0),([4,4],4)]),
 ("medium","group","Count occurrences of each string.",(group_a,group_b,group_c),[(["a","b","a"],{"a":2,"b":1}),([],{}),(["z"],{"z":1})]),
 ("medium","intervals","Sort and merge overlapping or touching closed intervals, retaining the maximum end.",(intervals_a,intervals_b,intervals_c),[([(2,5),(1,3),(5,7)],[(1,7)]),([(1,9),(2,3)],[(1,9)]),([],[])]),
 ("complex","path","Normalize a list of path components. Ignore empty and dot, pop on dot-dot, return None if it would escape root.",(path_a,path_b,path_c),[(["a","b","..","c"],"a/c"),(["..","a"],None),([".","a",""],"a")]),
 ("complex","window","Return length of longest contiguous slice without repeated elements.",(window_a,window_b,window_c),[([1,2,1,3,4],4),([1,2,3,3,4,5],3),([],0)]),
 ("complex","topo","Return lexicographically sorted ready groups of a dependency graph, or None if cyclic.",(topo_a,topo_b,topo_c),[({"B":["C"],"A":[],"C":["A"]},["A","C","B"]),({"A":["B"],"B":["A"]},None),({},[])])
]


def cases():
    out=[]
    for cls,name,spec,candidates,tests in SPECS:
        choices=list(candidates)
        random.Random("nexus-repair-"+name).shuffle(choices)
        options=dict(zip(("A","B","C"),choices))
        snippets={key:textwrap.dedent(inspect.getsource(fn)).replace(fn.__name__,"repair",1)
                  for key,fn in options.items()}
        source={"specification":spec,"candidates":snippets,
                "unrelated_release_history":"\n".join(
                   f"Release {i}: UI icon color changed; packaging label reviewed; translation metadata refreshed."
                   for i in range(15))}
        out.append({"task":name,"class":cls,"source":source,"options":options,"tests":tests})
    return out


def verify(case,answer):
    if not isinstance(answer,dict) or set(answer)!={"candidate"} or not isinstance(answer["candidate"],str):
        return False
    fn=case["options"].get(answer["candidate"])
    if fn is None:return False
    try:
        return all(fn(value)==expected for value,expected in case["tests"])
    except Exception:
        return False
