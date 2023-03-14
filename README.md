# ext-builder
Docker image for building external dependencies

## To build the image

```
docker build -t ext-builder .
```

## To write an external dependency build script

Create a `build.py` file with contents such as:

```python
import race_ext_builder as builder

def get_cli_arguments():
    parser = builder.get_arg_parser(
        name="libname",
        version="1.0.0",
        revision=1,
        caller=__file__,
    )
    return builder.normalize_args(parser.parse_args())

if __name__ == "__main__":
    args = get_cli_arguments()
    builder.make_dirs(args)
    builder.setup_logger(args)

    builder.fetch_source(
        args=args,
        source=f"http://libname.com/{args.version}.tar.gz",
        extract="tar.gz",
    )

    builder.execute(args, [
        "make",
        "install",
        f"--prefix={args.install_dir}",
    ], cwd=args.source_dir)

    builder.create_package(args)
```

See [race_ext_builder.py](race_ext_builder.py) for more functions and all
options available.

## To build an external dependency

For the host platform & architecture:

```
ext-builder/build.py path/to/libname
```

For Android:

```
ext-builder/build.py path/to/libname --target android-arm64-v8a
```
